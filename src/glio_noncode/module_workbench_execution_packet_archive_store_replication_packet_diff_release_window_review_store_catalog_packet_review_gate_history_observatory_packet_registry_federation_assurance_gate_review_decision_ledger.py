"""Record append-only adjudication for an operational federation review queue.

The federation review queue is intentionally read-oriented: it says which
assurance finding or release-gate check needs attention.  This module adds the
smallest durable write model needed to operate that queue without changing the
underlying release gate.  A decision ledger stores bounded, path-free actions
against exact queue-item addresses, preserves optimistic head protection, and
replays the effective open/closed state of every item.

The ledger is not a replacement for the assurance gate.  Remediation can close
an operational item, but the ledger's release projection remains false when
the source queue was not release-ready.  A subsequent verified queue must be
created for a new release decision.  This keeps human adjudication auditable
without allowing a waiver to silently promote a blocked federation.

All public projections are deterministic and contain no source paths,
identities, timestamps, private payloads, or runtime attribution.  A durable
ledger package contains exactly ``manifest.json``, ``ledger.json``, and
``entries.json``.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review as review_model,
)
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

FederationReviewQueue = review_model.FederationReviewQueue
FederationReviewItem = review_model.FederationReviewItem
ReviewState = review_model.ReviewState
ReviewPriority = review_model.ReviewPriority
ReviewRecordType = review_model.ReviewRecordType

VERSION = review_model.VERSION + "-decision-ledger-v1"
BOUNDARY = "public_registry_federation_assurance_gate_review_decision_ledger"
DECISION_PREFIX = review_model.REVIEW_PREFIX + "-decision"
ENTRY_PREFIX = DECISION_PREFIX + "-entry"
LEDGER_PREFIX = DECISION_PREFIX + "-ledger"
ENTRIES_PREFIX = DECISION_PREFIX + "-entries"
MANIFEST_PREFIX = DECISION_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
LEDGER_NAME = "ledger.json"
ENTRIES_NAME = "entries.json"
FILES = (MANIFEST_NAME, LEDGER_NAME, ENTRIES_NAME)
DEFAULT_LEDGER_ID = "glio-noncode-observatory-registry-federation-review-decision-ledger"
MAX_ITEMS = review_model.MAX_ITEMS
MAX_ENTRIES = 1024
MAX_QUERY_ITEMS = 4096
DEFAULT_LIMIT = 50

_FORBIDDEN_KEYS = frozenset({"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"})


class DecisionAction(StrEnum):
    """Allowed append-only operations against a queue item."""

    ACKNOWLEDGE = "acknowledge"
    REMEDIATE = "remediate"
    WAIVE = "waive"
    ESCALATE = "escalate"
    REOPEN = "reopen"


class DecisionResult(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class DecisionLedgerState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _optional_text(value: Any, field: str, maximum: int = 4096) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be an address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _address(value, field)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int = MAX_QUERY_ITEMS, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field} must be an integer")
    if value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} has unknown fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in _FORBIDDEN_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _action(value: Any, field: str = "decision action") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in DecisionAction}:
        raise ValidationError(f"{field} is invalid")
    return value


def _result(value: Any, field: str = "decision result") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in DecisionResult}:
        raise ValidationError(f"{field} is invalid")
    return value


def _source_state(value: Any, field: str = "decision source state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in ReviewState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _priority(value: Any, field: str = "decision source priority") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in ReviewPriority}:
        raise ValidationError(f"{field} is invalid")
    return value


def _record_type(value: Any, field: str = "decision record type") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in ReviewRecordType}:
        raise ValidationError(f"{field} is invalid")
    return value


def _item_state(item: FederationReviewItem) -> str:
    return item.state


class FederationReviewDecisionEntry:
    """One immutable action in a review decision chain."""

    def __init__(
        self,
        ordinal: int,
        decision_id: str,
        previous_head_address: str | None,
        item_address: str,
        record_type: str,
        record_id: str,
        plane: str,
        kind: str,
        source_state: str,
        source_priority: str,
        action: str,
        result_state: str,
        rationale: str,
        evidence_address: str | None,
        supersedes_address: str | None,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.decision_id = decision_id
        self.previous_head_address = previous_head_address
        self.item_address = item_address
        self.record_type = record_type
        self.record_id = record_id
        self.plane = plane
        self.kind = kind
        self.source_state = source_state
        self.source_priority = source_priority
        self.action = action
        self.result_state = result_state
        self.rationale = rationale
        self.evidence_address = evidence_address
        self.supersedes_address = supersedes_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "decision ordinal", MAX_ENTRIES)
        _text(self.decision_id, "decision ID", 256)
        _optional_address(self.previous_head_address, "decision previous head address")
        _address(self.item_address, "decision item address")
        _record_type(self.record_type)
        _text(self.record_id, "decision record ID", 256)
        _text(self.plane, "decision plane", 128)
        _text(self.kind, "decision kind", 128)
        _source_state(self.source_state)
        _priority(self.source_priority)
        action = _action(self.action)
        result = _result(self.result_state)
        _text(self.rationale, "decision rationale", 2048)
        _optional_address(self.evidence_address, "decision evidence address")
        _optional_address(self.supersedes_address, "decision supersedes address")
        if self.ordinal == 0 and self.previous_head_address is not None:
            raise ValidationError("first decision cannot have a previous head")
        if self.ordinal > 0 and self.previous_head_address is None:
            raise ValidationError("non-first decision requires a previous head")
        if action == DecisionAction.ACKNOWLEDGE.value:
            if self.source_state != ReviewState.CLEAR.value or result != DecisionResult.CLOSED.value:
                raise ValidationError("acknowledge requires a clear source and closed result")
        elif action == DecisionAction.REMEDIATE.value:
            if self.source_state == ReviewState.CLEAR.value or result != DecisionResult.CLOSED.value or self.evidence_address is None:
                raise ValidationError("remediate requires an open source, evidence, and closed result")
        elif action == DecisionAction.WAIVE.value:
            if self.source_state != ReviewState.REVIEW.value or self.source_priority == ReviewPriority.CRITICAL.value or result != DecisionResult.CLOSED.value:
                raise ValidationError("waive is limited to non-critical review items")
        elif action == DecisionAction.ESCALATE.value:
            if self.source_state == ReviewState.CLEAR.value or result != DecisionResult.OPEN.value:
                raise ValidationError("escalate requires an open source and open result")
        elif action == DecisionAction.REOPEN.value:
            if result != DecisionResult.OPEN.value or self.supersedes_address is None:
                raise ValidationError("reopen requires an open result and superseded decision")
        if not _public(self.to_dict()):
            raise ValidationError("decision entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "decision_id": self.decision_id,
            "previous_head_address": self.previous_head_address,
            "item_address": self.item_address,
            "record_type": self.record_type,
            "record_id": self.record_id,
            "plane": self.plane,
            "kind": self.kind,
            "source_state": self.source_state,
            "source_priority": self.source_priority,
            "action": self.action,
            "result_state": self.result_state,
            "rationale": self.rationale,
            "evidence_address": self.evidence_address,
            "supersedes_address": self.supersedes_address,
            "content_address": self.content_address,
        }


def address_decision_entry(value: FederationReviewDecisionEntry) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def _initial_state(item: FederationReviewItem) -> str:
    return DecisionResult.CLOSED.value if _item_state(item) == ReviewState.CLEAR.value else DecisionResult.OPEN.value


def _latest_by_item(items: Sequence[FederationReviewItem], entries: Sequence[FederationReviewDecisionEntry]) -> dict[str, FederationReviewDecisionEntry]:
    latest: dict[str, FederationReviewDecisionEntry] = {}
    for entry in entries:
        latest[entry.item_address] = entry
    return latest


def _effective_states(items: Sequence[FederationReviewItem], entries: Sequence[FederationReviewDecisionEntry]) -> dict[str, str]:
    states = {item.content_address: _initial_state(item) for item in items}
    for entry in entries:
        if entry.item_address not in states:
            raise ValidationError("decision entry references an unknown queue item")
        states[entry.item_address] = entry.result_state
    return states


def _ledger_counts(items: Sequence[FederationReviewItem], entries: Sequence[FederationReviewDecisionEntry]) -> dict[str, int]:
    latest = _latest_by_item(items, entries)
    states = _effective_states(items, entries)
    covered = sum(item.content_address in latest for item in items)
    open_count = sum(state == DecisionResult.OPEN.value for state in states.values())
    closed_count = sum(state == DecisionResult.CLOSED.value for state in states.values())
    unreviewed = sum(item.state != ReviewState.CLEAR.value and item.content_address not in latest for item in items)
    escalated = sum(
        state == DecisionResult.OPEN.value and latest.get(item.content_address, None) is not None and latest[item.content_address].action == DecisionAction.ESCALATE.value
        for item, state in ((item, states[item.content_address]) for item in items)
    )
    blocked = sum(
        states[item.content_address] == DecisionResult.OPEN.value and item.state == ReviewState.BLOCKED.value
        for item in items
    )
    return {"covered": covered, "open": open_count, "closed": closed_count, "unreviewed": unreviewed, "escalated": escalated, "blocked": blocked}


def _state_for_counts(counts: Mapping[str, int]) -> str:
    if counts["blocked"]:
        return DecisionLedgerState.BLOCKED.value
    if counts["open"]:
        return DecisionLedgerState.OPEN.value
    return DecisionLedgerState.CLOSED.value


class FederationReviewDecisionLedger:
    """Replayable decision state for one immutable review queue."""

    def __init__(
        self,
        ledger_id: str,
        version: str,
        boundary: str,
        federation_id: str,
        queue_id: str,
        queue_address: str,
        queue_state: str,
        gate_state: str,
        queue_release_ready: bool,
        item_count: int,
        entry_count: int,
        covered_count: int,
        open_count: int,
        closed_count: int,
        unreviewed_count: int,
        escalated_count: int,
        blocked_count: int,
        state: str,
        accepted: bool,
        release_ready: bool,
        items: Sequence[FederationReviewItem],
        entries: Sequence[FederationReviewDecisionEntry],
        head_address: str | None,
        content_address: str,
    ) -> None:
        self.ledger_id = ledger_id
        self.version = version
        self.boundary = boundary
        self.federation_id = federation_id
        self.queue_id = queue_id
        self.queue_address = queue_address
        self.queue_state = queue_state
        self.gate_state = gate_state
        self.queue_release_ready = queue_release_ready
        self.item_count = item_count
        self.entry_count = entry_count
        self.covered_count = covered_count
        self.open_count = open_count
        self.closed_count = closed_count
        self.unreviewed_count = unreviewed_count
        self.escalated_count = escalated_count
        self.blocked_count = blocked_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.items = tuple(items)
        self.entries = tuple(entries)
        self.head_address = head_address
        self.content_address = content_address
        self.queue: FederationReviewQueue | None = None
        self._validate()

    def _validate(self) -> None:
        _text(self.ledger_id, "decision ledger ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("decision ledger contract is invalid")
        _text(self.federation_id, "decision federation ID", 256)
        _text(self.queue_id, "decision queue ID", 256)
        _address(self.queue_address, "decision queue address")
        if self.queue_state not in {item.value for item in DecisionLedgerState} and self.queue_state not in {"clear", "review", "blocked"}:
            raise ValidationError("decision queue state is invalid")
        if self.gate_state not in {"promote", "hold", "block"}:
            raise ValidationError("decision gate state is invalid")
        _bool(self.queue_release_ready, "decision queue release-ready flag")
        _count(self.item_count, "decision item count", MAX_ITEMS, positive=True)
        _count(self.entry_count, "decision entry count", MAX_ENTRIES)
        for count, field in ((self.covered_count, "covered count"), (self.open_count, "open count"), (self.closed_count, "closed count"), (self.unreviewed_count, "unreviewed count"), (self.escalated_count, "escalated count"), (self.blocked_count, "blocked count")):
            _count(count, f"decision {field}", MAX_ITEMS)
        _count(len(self.entries), "decision entries", MAX_ENTRIES)
        if self.item_count != len(self.items) or self.item_count == 0:
            raise ValidationError("decision item count is not conserved")
        addresses: set[str] = set()
        source_states = {item.state for item in self.items}
        expected_queue_state = "blocked" if "blocked" in source_states else "review" if "review" in source_states else "clear"
        if self.queue_state != expected_queue_state:
            raise ValidationError("decision queue state is not conserved")
        if self.queue_release_ready != (self.queue_state == "clear"):
            raise ValidationError("decision queue readiness is not conserved")
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, FederationReviewItem) or item.ordinal != ordinal:
                raise ValidationError("decision queue item ordinals are not contiguous")
            if address_decision_item(item) != item.content_address:
                raise ValidationError("decision item address mismatch")
            if item.content_address in addresses:
                raise ValidationError("decision queue item addresses are not unique")
            addresses.add(item.content_address)
        if self.entry_count != len(self.entries):
            raise ValidationError("decision entry count is not conserved")
        entry_addresses: set[str] = set()
        decision_ids: set[str] = set()
        for ordinal, entry in enumerate(self.entries):
            if not isinstance(entry, FederationReviewDecisionEntry) or entry.ordinal != ordinal:
                raise ValidationError("decision entry ordinals are not contiguous")
            if entry.item_address not in addresses:
                raise ValidationError("decision entry item is outside the queue")
            if ordinal == 0 and entry.previous_head_address is not None:
                raise ValidationError("decision chain starts with a previous head")
            if ordinal > 0 and entry.previous_head_address != self.entries[ordinal - 1].content_address:
                raise ValidationError("decision chain is discontinuous")
            if address_decision_entry(entry) != entry.content_address:
                raise ValidationError("decision entry address mismatch")
            if entry.content_address in entry_addresses:
                raise ValidationError("decision entry addresses are not unique")
            if entry.decision_id in decision_ids:
                raise ValidationError("decision IDs are not unique")
            entry_addresses.add(entry.content_address)
            decision_ids.add(entry.decision_id)
            item = next(item for item in self.items if item.content_address == entry.item_address)
            if (entry.record_type, entry.record_id, entry.plane, entry.kind, entry.source_state, entry.source_priority) != (item.record_type, item.record_id, item.plane, item.kind, item.state, item.priority):
                raise ValidationError("decision entry does not match its queue item")
        if self.head_address != (self.entries[-1].content_address if self.entries else None):
            raise ValidationError("decision head is not the final entry")
        counts = _ledger_counts(self.items, self.entries)
        if (self.covered_count, self.open_count, self.closed_count, self.unreviewed_count, self.escalated_count, self.blocked_count) != (counts["covered"], counts["open"], counts["closed"], counts["unreviewed"], counts["escalated"], counts["blocked"]):
            raise ValidationError("decision counts are not conserved")
        expected_state = _state_for_counts(counts)
        if self.state != expected_state:
            raise ValidationError("decision ledger state is invalid")
        if self.accepted != (self.blocked_count == 0):
            raise ValidationError("decision ledger acceptance is invalid")
        expected_release_ready = self.queue_release_ready and self.state == DecisionLedgerState.CLOSED.value
        if self.release_ready != expected_release_ready:
            raise ValidationError("decision release readiness is invalid")
        _optional_address(self.head_address, "decision head address")
        if not _public(self.to_dict()):
            raise ValidationError("decision ledger crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "version": self.version,
            "boundary": self.boundary,
            "federation_id": self.federation_id,
            "queue_id": self.queue_id,
            "queue_address": self.queue_address,
            "queue_state": self.queue_state,
            "gate_state": self.gate_state,
            "queue_release_ready": self.queue_release_ready,
            "item_count": self.item_count,
            "entry_count": self.entry_count,
            "covered_count": self.covered_count,
            "open_count": self.open_count,
            "closed_count": self.closed_count,
            "unreviewed_count": self.unreviewed_count,
            "escalated_count": self.escalated_count,
            "blocked_count": self.blocked_count,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "head_address": self.head_address,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_items: bool = True, include_entries: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        if include_entries:
            body["entries"] = [entry.to_dict() for entry in self.entries]
        return body


def address_decision_item(value: FederationReviewItem) -> str:
    return review_model.address_review_item(value)


def address_decision_entries(value: FederationReviewDecisionLedger) -> str:
    return content_hash({"ledger_id": value.ledger_id, "entries": [entry.to_dict() for entry in value.entries]}, prefix=ENTRIES_PREFIX)


def address_decision_ledger(value: FederationReviewDecisionLedger) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=LEDGER_PREFIX)


def _ledger_body(queue: FederationReviewQueue, entries: Sequence[FederationReviewDecisionEntry], ledger_id: str) -> dict[str, Any]:
    counts = _ledger_counts(queue.items, entries)
    state = _state_for_counts(counts)
    return {
        "ledger_id": _text(ledger_id, "decision ledger ID", 256),
        "version": VERSION,
        "boundary": BOUNDARY,
        "federation_id": queue.federation_id,
        "queue_id": queue.queue_id,
        "queue_address": queue.content_address,
        "queue_state": queue.state,
        "gate_state": queue.gate_state,
        "queue_release_ready": queue.release_ready,
        "item_count": len(queue.items),
        "entry_count": len(entries),
        "covered_count": counts["covered"],
        "open_count": counts["open"],
        "closed_count": counts["closed"],
        "unreviewed_count": counts["unreviewed"],
        "escalated_count": counts["escalated"],
        "blocked_count": counts["blocked"],
        "state": state,
        "accepted": counts["blocked"] == 0,
        "release_ready": queue.release_ready and state == DecisionLedgerState.CLOSED.value,
        "items": tuple(queue.items),
        "entries": tuple(entries),
        "head_address": entries[-1].content_address if entries else None,
    }


def build_decision_ledger(queue: FederationReviewQueue, *, ledger_id: str = DEFAULT_LEDGER_ID) -> FederationReviewDecisionLedger:
    if not isinstance(queue, FederationReviewQueue):
        raise ValidationError("decision ledger requires a typed review queue")
    review_model.verify_review_queue(queue)
    body = _ledger_body(queue, (), ledger_id)
    provisional = FederationReviewDecisionLedger(**body, content_address="pending:ledger")
    value = FederationReviewDecisionLedger(**body, content_address=address_decision_ledger(provisional))
    value.queue = queue
    return value


def _rebuild_ledger(value: FederationReviewDecisionLedger, entries: Sequence[FederationReviewDecisionEntry]) -> FederationReviewDecisionLedger:
    body = {
        "ledger_id": value.ledger_id,
        "version": value.version,
        "boundary": value.boundary,
        "federation_id": value.federation_id,
        "queue_id": value.queue_id,
        "queue_address": value.queue_address,
        "queue_state": value.queue_state,
        "gate_state": value.gate_state,
        "queue_release_ready": value.queue_release_ready,
        "items": value.items,
        "entries": tuple(entries),
    }
    counts = _ledger_counts(value.items, entries)
    state = _state_for_counts(counts)
    body.update({"item_count": len(value.items), "entry_count": len(entries), "covered_count": counts["covered"], "open_count": counts["open"], "closed_count": counts["closed"], "unreviewed_count": counts["unreviewed"], "escalated_count": counts["escalated"], "blocked_count": counts["blocked"], "state": state, "accepted": counts["blocked"] == 0, "release_ready": value.queue_release_ready and state == DecisionLedgerState.CLOSED.value, "head_address": entries[-1].content_address if entries else None})
    provisional = FederationReviewDecisionLedger(**body, content_address="pending:ledger")
    result = FederationReviewDecisionLedger(**body, content_address=address_decision_ledger(provisional))
    result.queue = value.queue
    return result


def _find_item(value: FederationReviewDecisionLedger, item_address: str) -> FederationReviewItem:
    item_address = _address(item_address, "decision item address")
    for item in value.items:
        if item.content_address == item_address:
            return item
    raise ValidationError("decision item address is not in the queue")


def append_decision(
    ledger: FederationReviewDecisionLedger,
    item: FederationReviewItem,
    action: str,
    rationale: str,
    *,
    evidence_address: str | None = None,
    expected_head_address: str | None = None,
    decision_id: str | None = None,
) -> FederationReviewDecisionLedger:
    verify_decision_ledger(ledger)
    if not isinstance(item, FederationReviewItem):
        raise ValidationError("decision item must be typed")
    selected = _find_item(ledger, item.content_address)
    if selected.to_dict() != item.to_dict():
        raise ValidationError("decision item does not match the ledger snapshot")
    if expected_head_address is not None and expected_head_address != ledger.head_address:
        raise ValidationError("decision expected head does not match")
    action = _action(action)
    rationale = _text(rationale, "decision rationale", 2048)
    evidence_address = _optional_address(evidence_address, "decision evidence address")
    current = _effective_states(ledger.items, ledger.entries)[item.content_address]
    latest = _latest_by_item(ledger.items, ledger.entries).get(item.content_address)
    if action == DecisionAction.ACKNOWLEDGE.value:
        if selected.state != ReviewState.CLEAR.value or current != DecisionResult.CLOSED.value:
            raise ValidationError("acknowledge requires an unmodified clear item")
        result_state = DecisionResult.CLOSED.value
        supersedes = None
    elif action == DecisionAction.REMEDIATE.value:
        if current != DecisionResult.OPEN.value or evidence_address is None:
            raise ValidationError("remediate requires an open item and evidence address")
        result_state = DecisionResult.CLOSED.value
        supersedes = latest.content_address if latest is not None else None
    elif action == DecisionAction.WAIVE.value:
        if current != DecisionResult.OPEN.value or selected.state != ReviewState.REVIEW.value or selected.priority == ReviewPriority.CRITICAL.value:
            raise ValidationError("waive requires a non-critical open warning item")
        result_state = DecisionResult.CLOSED.value
        supersedes = latest.content_address if latest is not None else None
    elif action == DecisionAction.ESCALATE.value:
        if current != DecisionResult.OPEN.value or selected.state == ReviewState.CLEAR.value:
            raise ValidationError("escalate requires an open item")
        result_state = DecisionResult.OPEN.value
        supersedes = latest.content_address if latest is not None else None
    else:
        if current != DecisionResult.CLOSED.value or latest is None:
            raise ValidationError("reopen requires a closed item with a prior decision")
        result_state = DecisionResult.OPEN.value
        supersedes = latest.content_address
    entry_body = {
        "ordinal": len(ledger.entries),
        "decision_id": decision_id or f"{ledger.ledger_id}:decision:{len(ledger.entries)}",
        "previous_head_address": ledger.head_address,
        "item_address": selected.content_address,
        "record_type": selected.record_type,
        "record_id": selected.record_id,
        "plane": selected.plane,
        "kind": selected.kind,
        "source_state": selected.state,
        "source_priority": selected.priority,
        "action": action,
        "result_state": result_state,
        "rationale": rationale,
        "evidence_address": evidence_address,
        "supersedes_address": supersedes,
    }
    provisional = FederationReviewDecisionEntry(**entry_body, content_address="pending:entry")
    entry = FederationReviewDecisionEntry(**entry_body, content_address=address_decision_entry(provisional))
    return _rebuild_ledger(ledger, ledger.entries + (entry,))


def append_decision_by_address(
    ledger: FederationReviewDecisionLedger,
    item_address: str,
    action: str,
    rationale: str,
    *,
    evidence_address: str | None = None,
    expected_head_address: str | None = None,
    decision_id: str | None = None,
) -> FederationReviewDecisionLedger:
    return append_decision(ledger, _find_item(ledger, item_address), action, rationale, evidence_address=evidence_address, expected_head_address=expected_head_address, decision_id=decision_id)


def verify_decision_ledger(value: FederationReviewDecisionLedger) -> FederationReviewDecisionLedger:
    if not isinstance(value, FederationReviewDecisionLedger):
        raise ValidationError("decision ledger verification requires a typed ledger")
    for item in value.items:
        if address_decision_item(item) != item.content_address:
            raise ValidationError("decision item address mismatch")
    for entry in value.entries:
        if address_decision_entry(entry) != entry.content_address:
            raise ValidationError("decision entry address mismatch")
    if address_decision_ledger(value) != value.content_address:
        raise ValidationError("decision ledger address mismatch")
    return value


class DecisionDiffAction(StrEnum):
    """Stable classification for two decision-ledger snapshots."""

    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


def _optional_state(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _result(value, field)


def _optional_action(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _action(value, field)


def _diff_action(value: Any, field: str = "decision diff action") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in DecisionDiffAction}:
        raise ValidationError(f"{field} is invalid")
    return value


class FederationReviewDecisionDiffItem:
    """One path-free item comparison between decision snapshots."""

    def __init__(
        self,
        ordinal: int,
        action: str,
        key: str,
        item_address: str,
        record_type: str,
        record_id: str,
        plane: str,
        kind: str,
        baseline_state: str | None,
        candidate_state: str | None,
        baseline_action: str | None,
        candidate_action: str | None,
        baseline_decision_address: str | None,
        candidate_decision_address: str | None,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.action = action
        self.key = key
        self.item_address = item_address
        self.record_type = record_type
        self.record_id = record_id
        self.plane = plane
        self.kind = kind
        self.baseline_state = baseline_state
        self.candidate_state = candidate_state
        self.baseline_action = baseline_action
        self.candidate_action = candidate_action
        self.baseline_decision_address = baseline_decision_address
        self.candidate_decision_address = candidate_decision_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "decision diff ordinal", MAX_ITEMS * 2)
        _diff_action(self.action)
        _text(self.key, "decision diff key", 512)
        _address(self.item_address, "decision diff item address")
        _record_type(self.record_type, "decision diff record type")
        _text(self.record_id, "decision diff record ID", 256)
        _text(self.plane, "decision diff plane", 128)
        _text(self.kind, "decision diff kind", 128)
        baseline_state = _optional_state(self.baseline_state, "decision diff baseline state")
        candidate_state = _optional_state(self.candidate_state, "decision diff candidate state")
        baseline_action = _optional_action(self.baseline_action, "decision diff baseline action")
        candidate_action = _optional_action(self.candidate_action, "decision diff candidate action")
        _optional_address(self.baseline_decision_address, "decision diff baseline decision address")
        _optional_address(self.candidate_decision_address, "decision diff candidate decision address")
        if self.action == DecisionDiffAction.ADDED.value:
            if baseline_state is not None or baseline_action is not None or self.baseline_decision_address is not None or candidate_state is None:
                raise ValidationError("added decision diff item has invalid baseline fields")
        elif self.action == DecisionDiffAction.REMOVED.value:
            if candidate_state is not None or candidate_action is not None or self.candidate_decision_address is not None or baseline_state is None:
                raise ValidationError("removed decision diff item has invalid candidate fields")
        elif self.action == DecisionDiffAction.UNCHANGED.value:
            if baseline_state is None or candidate_state is None or baseline_state != candidate_state or baseline_action != candidate_action:
                raise ValidationError("unchanged decision diff item has differing fields")
        elif baseline_state is None or candidate_state is None or baseline_state == candidate_state and baseline_action == candidate_action:
            raise ValidationError("changed decision diff item has no semantic change")
        if not _public(self.to_dict()):
            raise ValidationError("decision diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "action": self.action,
            "key": self.key,
            "item_address": self.item_address,
            "record_type": self.record_type,
            "record_id": self.record_id,
            "plane": self.plane,
            "kind": self.kind,
            "baseline_state": self.baseline_state,
            "candidate_state": self.candidate_state,
            "baseline_action": self.baseline_action,
            "candidate_action": self.candidate_action,
            "baseline_decision_address": self.baseline_decision_address,
            "candidate_decision_address": self.candidate_decision_address,
            "content_address": self.content_address,
        }


def address_decision_diff_item(value: FederationReviewDecisionDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DECISION_PREFIX + "-diff-item")


class FederationReviewDecisionDiff:
    """Deterministic comparison of two append-only decision snapshots."""

    def __init__(
        self,
        diff_id: str,
        version: str,
        boundary: str,
        federation_id: str,
        baseline_ledger_id: str,
        candidate_ledger_id: str,
        baseline_ledger_address: str,
        candidate_ledger_address: str,
        baseline_state: str,
        candidate_state: str,
        item_count: int,
        added_count: int,
        removed_count: int,
        unchanged_count: int,
        changed_count: int,
        resolved_count: int,
        state: str,
        accepted: bool,
        release_ready: bool,
        items: Sequence[FederationReviewDecisionDiffItem],
        content_address: str,
    ) -> None:
        self.diff_id = diff_id
        self.version = version
        self.boundary = boundary
        self.federation_id = federation_id
        self.baseline_ledger_id = baseline_ledger_id
        self.candidate_ledger_id = candidate_ledger_id
        self.baseline_ledger_address = baseline_ledger_address
        self.candidate_ledger_address = candidate_ledger_address
        self.baseline_state = baseline_state
        self.candidate_state = candidate_state
        self.item_count = item_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.resolved_count = resolved_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "decision diff ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("decision diff contract is invalid")
        _text(self.federation_id, "decision diff federation ID", 256)
        _text(self.baseline_ledger_id, "decision diff baseline ledger ID", 256)
        _text(self.candidate_ledger_id, "decision diff candidate ledger ID", 256)
        _address(self.baseline_ledger_address, "decision diff baseline ledger address")
        _address(self.candidate_ledger_address, "decision diff candidate ledger address")
        _result(self.baseline_state, "decision diff baseline state")
        _result(self.candidate_state, "decision diff candidate state")
        if self.state not in {"improved", "regressed", "changed", "unchanged"}:
            raise ValidationError("decision diff state is invalid")
        _bool(self.accepted, "decision diff acceptance")
        _bool(self.release_ready, "decision diff release readiness")
        _count(self.item_count, "decision diff item count", MAX_ITEMS * 2)
        if self.item_count != len(self.items):
            raise ValidationError("decision diff item count is not conserved")
        for count, field in ((self.added_count, "added count"), (self.removed_count, "removed count"), (self.unchanged_count, "unchanged count"), (self.changed_count, "changed count"), (self.resolved_count, "resolved count")):
            _count(count, f"decision diff {field}", MAX_ITEMS * 2)
        if self.item_count != self.added_count + self.removed_count + self.unchanged_count + self.changed_count:
            raise ValidationError("decision diff action counts are not conserved")
        addresses: set[str] = set()
        keys: set[str] = set()
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, FederationReviewDecisionDiffItem) or item.ordinal != ordinal:
                raise ValidationError("decision diff ordinals are not contiguous")
            if address_decision_diff_item(item) != item.content_address:
                raise ValidationError("decision diff item address mismatch")
            if item.key in keys:
                raise ValidationError("decision diff keys are not unique")
            if item.content_address in addresses:
                raise ValidationError("decision diff item addresses are not unique")
            keys.add(item.key)
            addresses.add(item.content_address)
        expected_resolved = sum(item.baseline_state == DecisionResult.OPEN.value and item.candidate_state == DecisionResult.CLOSED.value for item in self.items)
        if self.resolved_count != expected_resolved:
            raise ValidationError("decision diff resolved count is not conserved")
        if self.changed_count == 0 and self.added_count == 0 and self.removed_count == 0:
            expected_state = "unchanged"
        elif self.candidate_state == DecisionResult.CLOSED.value and self.baseline_state != DecisionResult.CLOSED.value:
            expected_state = "improved"
        elif self.baseline_state == DecisionResult.CLOSED.value and self.candidate_state != DecisionResult.CLOSED.value:
            expected_state = "regressed"
        else:
            expected_state = "changed"
        if self.state != expected_state:
            raise ValidationError("decision diff state is not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("decision diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "federation_id": self.federation_id, "baseline_ledger_id": self.baseline_ledger_id, "candidate_ledger_id": self.candidate_ledger_id, "baseline_ledger_address": self.baseline_ledger_address, "candidate_ledger_address": self.candidate_ledger_address, "baseline_state": self.baseline_state, "candidate_state": self.candidate_state, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "resolved_count": self.resolved_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def _semantic_item(value: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(value.get(field) for field in ("record_type", "record_id", "plane", "kind", "source_state", "source_priority", "state", "action", "rationale", "evidence_address"))


def build_decision_diff(baseline: FederationReviewDecisionLedger, candidate: FederationReviewDecisionLedger, *, diff_id: str = "glio-noncode-observatory-registry-federation-review-decision-diff") -> FederationReviewDecisionDiff:
    verify_decision_ledger(baseline)
    verify_decision_ledger(candidate)
    baseline_map = {item.content_address: _item_projection(baseline, item) for item in baseline.items}
    candidate_map = {item.content_address: _item_projection(candidate, item) for item in candidate.items}
    rows: list[FederationReviewDecisionDiffItem] = []
    for ordinal, key in enumerate(sorted(set(baseline_map) | set(candidate_map))):
        left = baseline_map.get(key)
        right = candidate_map.get(key)
        if left is None:
            action = DecisionDiffAction.ADDED.value
            source = right
        elif right is None:
            action = DecisionDiffAction.REMOVED.value
            source = left
        else:
            action = DecisionDiffAction.UNCHANGED.value if _semantic_item(left) == _semantic_item(right) else DecisionDiffAction.CHANGED.value
            source = right
        body = {"ordinal": ordinal, "action": action, "key": key, "item_address": key, "record_type": source["record_type"], "record_id": source["record_id"], "plane": source["plane"], "kind": source["kind"], "baseline_state": left["state"] if left else None, "candidate_state": right["state"] if right else None, "baseline_action": left["action"] if left else None, "candidate_action": right["action"] if right else None, "baseline_decision_address": left["decision_address"] if left else None, "candidate_decision_address": right["decision_address"] if right else None}
        provisional = FederationReviewDecisionDiffItem(**body, content_address="pending:diff-item")
        rows.append(FederationReviewDecisionDiffItem(**body, content_address=address_decision_diff_item(provisional)))
    changed_count = sum(item.action == DecisionDiffAction.CHANGED.value for item in rows)
    added_count = sum(item.action == DecisionDiffAction.ADDED.value for item in rows)
    removed_count = sum(item.action == DecisionDiffAction.REMOVED.value for item in rows)
    unchanged_count = sum(item.action == DecisionDiffAction.UNCHANGED.value for item in rows)
    state = "unchanged" if not changed_count and not added_count and not removed_count else "improved" if candidate.state == DecisionLedgerState.CLOSED.value and baseline.state != DecisionLedgerState.CLOSED.value else "regressed" if baseline.state == DecisionLedgerState.CLOSED.value and candidate.state != DecisionLedgerState.CLOSED.value else "changed"
    body = {"diff_id": _text(diff_id, "decision diff ID", 256), "version": VERSION, "boundary": BOUNDARY, "federation_id": candidate.federation_id, "baseline_ledger_id": baseline.ledger_id, "candidate_ledger_id": candidate.ledger_id, "baseline_ledger_address": baseline.content_address, "candidate_ledger_address": candidate.content_address, "baseline_state": baseline.state, "candidate_state": candidate.state, "item_count": len(rows), "added_count": added_count, "removed_count": removed_count, "unchanged_count": unchanged_count, "changed_count": changed_count, "resolved_count": sum(item.baseline_state == DecisionResult.OPEN.value and item.candidate_state == DecisionResult.CLOSED.value for item in rows), "state": state, "accepted": baseline.accepted and candidate.accepted, "release_ready": candidate.release_ready, "items": tuple(rows)}
    provisional = FederationReviewDecisionDiff(**body, content_address="pending:diff")
    return FederationReviewDecisionDiff(**body, content_address=address_decision_diff(provisional))


def address_decision_diff(value: FederationReviewDecisionDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DECISION_PREFIX + "-diff")


def verify_decision_diff(value: FederationReviewDecisionDiff) -> FederationReviewDecisionDiff:
    if not isinstance(value, FederationReviewDecisionDiff):
        raise ValidationError("decision diff verification requires a typed diff")
    for item in value.items:
        if address_decision_diff_item(item) != item.content_address:
            raise ValidationError("decision diff item address mismatch")
    if address_decision_diff(value) != value.content_address:
        raise ValidationError("decision diff address mismatch")
    return value


def decision_diff_item_from_mapping(value: Mapping[str, Any]) -> FederationReviewDecisionDiffItem:
    body = dict(_mapping(value, "decision diff item"))
    _strict(body, {"ordinal", "action", "key", "item_address", "record_type", "record_id", "plane", "kind", "baseline_state", "candidate_state", "baseline_action", "candidate_action", "baseline_decision_address", "candidate_decision_address", "content_address"}, "decision diff item")
    return FederationReviewDecisionDiffItem(**body)


def decision_diff_from_mapping(value: Mapping[str, Any]) -> FederationReviewDecisionDiff:
    body = dict(_mapping(value, "decision diff"))
    _strict(body, {"diff_id", "version", "boundary", "federation_id", "baseline_ledger_id", "candidate_ledger_id", "baseline_ledger_address", "candidate_ledger_address", "baseline_state", "candidate_state", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "resolved_count", "state", "accepted", "release_ready", "items", "content_address"}, "decision diff")
    items = tuple(decision_diff_item_from_mapping(item) for item in _mapping_sequence(body.pop("items"), "decision diff items"))
    return verify_decision_diff(FederationReviewDecisionDiff(**body, items=items))


def decision_entry_from_mapping(value: Mapping[str, Any]) -> FederationReviewDecisionEntry:
    body = dict(_mapping(value, "decision entry"))
    _strict(body, {"ordinal", "decision_id", "previous_head_address", "item_address", "record_type", "record_id", "plane", "kind", "source_state", "source_priority", "action", "result_state", "rationale", "evidence_address", "supersedes_address", "content_address"}, "decision entry")
    return FederationReviewDecisionEntry(**body)


def decision_ledger_from_mapping(value: Mapping[str, Any]) -> FederationReviewDecisionLedger:
    body = dict(_mapping(value, "decision ledger"))
    _strict(body, {"ledger_id", "version", "boundary", "federation_id", "queue_id", "queue_address", "queue_state", "gate_state", "queue_release_ready", "item_count", "entry_count", "covered_count", "open_count", "closed_count", "unreviewed_count", "escalated_count", "blocked_count", "state", "accepted", "release_ready", "items", "entries", "head_address", "content_address"}, "decision ledger")
    items = tuple(review_model.federation_review_item_from_mapping(item) for item in _mapping_sequence(body.pop("items"), "decision items"))
    entries = tuple(decision_entry_from_mapping(item) for item in _mapping_sequence(body.pop("entries"), "decision entries"))
    result = FederationReviewDecisionLedger(**body, items=items, entries=entries)
    return verify_decision_ledger(result)


def _mapping_sequence(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    return tuple(_mapping(item, field) for item in value)


class DecisionQuery:
    def __init__(self, resource: str = "summary", *, state: str | None = None, action: str | None = None, record_type: str | None = None, plane: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "decision query resource", 64)
        allowed = {"summary", "entries", "items", "open", "closed", "escalated", "blockers", "added", "removed", "changed", "unchanged", "resolved"}
        if self.resource not in allowed:
            raise ValidationError("decision query resource is invalid")
        if state is not None and state not in {item.value for item in DecisionResult}:
            raise ValidationError("decision query state is invalid")
        if action is not None:
            action = _text(action, "decision query action", 32)
            if action not in {item.value for item in DecisionAction} | {item.value for item in DecisionDiffAction}:
                raise ValidationError("decision query action is invalid")
        if record_type is not None:
            _record_type(record_type, "decision query record type")
        self.state = state
        self.action = action
        self.record_type = record_type
        self.plane = _optional_text(plane, "decision query plane", 128)
        self.text = _optional_text(text, "decision query text", 256).casefold() if text is not None else None
        self.offset = _count(offset, "decision query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "decision query limit", MAX_QUERY_ITEMS, positive=True)
        if self.offset + self.limit > MAX_QUERY_ITEMS:
            raise ValidationError("decision query window is too large")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "state": self.state, "action": self.action, "record_type": self.record_type, "plane": self.plane, "text": self.text, "offset": self.offset, "limit": self.limit}


class DecisionQueryResult:
    def __init__(self, query: DecisionQuery, total_count: int, items: Sequence[Mapping[str, Any]], source_address: str) -> None:
        self.query = query
        self.total_count = total_count
        self.items = tuple(dict(item) for item in items)
        self.returned_count = len(self.items)
        self.source_address = _address(source_address, "decision query source address")
        self.content_address = "pending:query"
        self.content_address = content_hash(self.to_dict() | {"content_address": None}, prefix=DECISION_PREFIX + "-query-result")
        self._validate()

    def _validate(self) -> None:
        _count(self.total_count, "decision query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "decision query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count:
            raise ValidationError("decision query returned count exceeds total")
        if not _public(self.to_dict()):
            raise ValidationError("decision query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "source_address": self.source_address, "content_address": self.content_address}


def _item_projection(ledger: FederationReviewDecisionLedger, item: FederationReviewItem) -> dict[str, Any]:
    latest = _latest_by_item(ledger.items, ledger.entries).get(item.content_address)
    state = _effective_states(ledger.items, ledger.entries)[item.content_address]
    return {"ordinal": item.ordinal, "item_address": item.content_address, "record_type": item.record_type, "record_id": item.record_id, "plane": item.plane, "kind": item.kind, "source_state": item.state, "source_priority": item.priority, "state": state, "action": latest.action if latest else None, "decision_address": latest.content_address if latest else None, "rationale": latest.rationale if latest else None, "evidence_address": latest.evidence_address if latest else None, "covered": latest is not None}


def _matches(value: Mapping[str, Any], query: DecisionQuery) -> bool:
    if query.state is not None and value.get("state") != query.state:
        return False
    if query.action is not None and value.get("action") != query.action:
        return False
    if query.record_type is not None and value.get("record_type") != query.record_type:
        return False
    if query.plane is not None and value.get("plane") != query.plane:
        return False
    if query.text is not None and query.text not in canonical_json(value).casefold():
        return False
    return True


def query_decision_ledger(value: FederationReviewDecisionLedger, query: DecisionQuery | None = None, **kwargs: Any) -> DecisionQueryResult:
    verify_decision_ledger(value)
    selected = query if query is not None else DecisionQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    if selected.resource == "summary":
        records = (value.summary(),)
    elif selected.resource == "entries":
        records = tuple(entry.to_dict() for entry in value.entries)
    else:
        records = tuple(_item_projection(value, item) for item in value.items)
        if selected.resource == "open":
            records = tuple(item for item in records if item["state"] == DecisionResult.OPEN.value)
        elif selected.resource == "closed":
            records = tuple(item for item in records if item["state"] == DecisionResult.CLOSED.value)
        elif selected.resource == "escalated":
            records = tuple(item for item in records if item["action"] == DecisionAction.ESCALATE.value)
        elif selected.resource == "blockers":
            records = tuple(item for item in records if item["source_state"] == ReviewState.BLOCKED.value and item["state"] == DecisionResult.OPEN.value)
    matched = tuple(item for item in records if _matches(item, selected))
    return DecisionQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], value.content_address)


def query_decision_diff(value: FederationReviewDecisionDiff, query: DecisionQuery | None = None, **kwargs: Any) -> DecisionQueryResult:
    verify_decision_diff(value)
    selected = query if query is not None else DecisionQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    if selected.resource == "summary":
        records = (value.summary(),)
    else:
        records = tuple(item.to_dict() for item in value.items)
        if selected.resource in {item.value for item in DecisionDiffAction}:
            records = tuple(item for item in records if item["action"] == selected.resource)
        elif selected.resource == "resolved":
            records = tuple(item for item in records if item["baseline_state"] == DecisionResult.OPEN.value and item["candidate_state"] == DecisionResult.CLOSED.value)
    matched = tuple(item for item in records if _matches(item, selected))
    return DecisionQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], value.content_address)


def decision_ledger_json(value: FederationReviewDecisionLedger) -> str:
    verify_decision_ledger(value)
    return canonical_json(value.to_dict())


def decision_diff_json(value: FederationReviewDecisionDiff) -> str:
    verify_decision_diff(value)
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field) for field in fields} for row in rows)
    return output.getvalue()


def decision_ledger_csv(value: FederationReviewDecisionLedger) -> str:
    verify_decision_ledger(value)
    rows = [entry.to_dict() for entry in value.entries]
    if not rows:
        return ""
    return _csv_text(rows, ("ordinal", "decision_id", "item_address", "record_type", "record_id", "plane", "kind", "source_state", "source_priority", "action", "result_state", "rationale", "evidence_address", "supersedes_address", "previous_head_address", "content_address"))


def decision_diff_csv(value: FederationReviewDecisionDiff) -> str:
    verify_decision_diff(value)
    rows = [item.to_dict() for item in value.items]
    if not rows:
        return ""
    return _csv_text(rows, ("ordinal", "action", "key", "item_address", "record_type", "record_id", "plane", "kind", "baseline_state", "candidate_state", "baseline_action", "candidate_action", "baseline_decision_address", "candidate_decision_address", "content_address"))


def decision_query_json(value: DecisionQueryResult) -> str:
    return canonical_json(value.to_dict())


def decision_query_csv(value: DecisionQueryResult) -> str:
    if not value.items:
        return ""
    return _csv_text(value.items, tuple(sorted({key for item in value.items for key in item})))


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", ""]
    lines.extend(f"- {key}: `{summary[key]}`" for key in sorted(summary))
    lines.extend(["", "## Records", ""])
    if not rows:
        lines.append("No records.")
        return "\n".join(lines) + "\n"
    fields = tuple(sorted({key for row in rows for key in row}))
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("| " + " | ".join("---" for _ in fields) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|").replace("\n", " ") for field in fields) + " |")
    return "\n".join(lines) + "\n"


def render_decision_ledger_markdown(value: FederationReviewDecisionLedger) -> str:
    verify_decision_ledger(value)
    return _markdown("Observatory Packet Registry Federation Review Decision Ledger", value.summary(), [entry.to_dict() for entry in value.entries])


def render_decision_diff_markdown(value: FederationReviewDecisionDiff) -> str:
    verify_decision_diff(value)
    return _markdown("Observatory Packet Registry Federation Review Decision Diff", value.summary(), [item.to_dict() for item in value.items])


def render_decision_query_markdown(value: DecisionQueryResult) -> str:
    return _markdown("Observatory Packet Registry Federation Review Decision Query", {"resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def _manifest_body(value: FederationReviewDecisionLedger, ledger_raw: bytes, entries_raw: bytes) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "ledger_id": value.ledger_id, "queue_id": value.queue_id, "queue_address": value.queue_address, "ledger_address": value.content_address, "entry_address": address_decision_entries(value), "artifact_count": 2, "files": list(FILES), "artifacts": [{"name": LEDGER_NAME, "bytes": len(ledger_raw), "byte_address": hash_bytes(ledger_raw), "file_address": content_hash({"name": LEDGER_NAME, "byte_address": hash_bytes(ledger_raw)}, prefix=DECISION_PREFIX + "-file")}, {"name": ENTRIES_NAME, "bytes": len(entries_raw), "byte_address": hash_bytes(entries_raw), "file_address": content_hash({"name": ENTRIES_NAME, "byte_address": hash_bytes(entries_raw)}, prefix=DECISION_PREFIX + "-file")}], "manifest_address": None}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=MANIFEST_PREFIX)


def _ledger_document(value: FederationReviewDecisionLedger) -> dict[str, Any]:
    return value.to_dict(include_entries=False)


def _entries_document(value: FederationReviewDecisionLedger) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "ledger_id": value.ledger_id, "ledger_address": value.content_address, "entry_count": value.entry_count, "entries_address": address_decision_entries(value), "entries": [entry.to_dict() for entry in value.entries]}


def write_decision_ledger(value: FederationReviewDecisionLedger, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_ledger(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("decision ledger destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    ledger_raw = canonical_bytes(_ledger_document(value))
    entries_raw = canonical_bytes(_entries_document(value))
    manifest_body = _manifest_body(value, ledger_raw, entries_raw)
    manifest_body["manifest_address"] = _manifest_address(manifest_body)
    manifest_raw = canonical_bytes(manifest_body)
    temporary = Path(tempfile.mkdtemp(prefix=f".{DECISION_PREFIX}-", dir=str(destination.parent)))
    try:
        (temporary / LEDGER_NAME).write_bytes(ledger_raw)
        (temporary / ENTRIES_NAME).write_bytes(entries_raw)
        (temporary / MANIFEST_NAME).write_bytes(manifest_raw)
        if destination.exists():
            if not destination.is_dir() or any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("decision ledger destination already exists")
                shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _read_json(path: Path, field: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{field} must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is invalid JSON") from exc
    if canonical_bytes(value) != raw:
        raise ValidationError(f"{field} is not canonical JSON")
    return dict(_mapping(value, field))


def _check_artifact(manifest: Mapping[str, Any], path: Path, name: str) -> None:
    artifacts = manifest["artifacts"]
    artifact = next((item for item in artifacts if item.get("name") == name), None)
    if artifact is None:
        raise ValidationError(f"decision manifest is missing {name}")
    raw = path.read_bytes()
    if artifact.get("bytes") != len(raw) or artifact.get("byte_address") != hash_bytes(raw):
        raise ValidationError(f"decision {name} bytes are not addressed")
    expected_file = content_hash({"name": name, "byte_address": hash_bytes(raw)}, prefix=DECISION_PREFIX + "-file")
    if artifact.get("file_address") != expected_file:
        raise ValidationError(f"decision {name} file address is invalid")


def load_decision_ledger(directory: str | Path) -> FederationReviewDecisionLedger:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("decision ledger input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(FILES):
        raise ValidationError("decision ledger file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "decision manifest")
    _strict(manifest, {"version", "boundary", "ledger_id", "queue_id", "queue_address", "ledger_address", "entry_address", "artifact_count", "files", "artifacts", "manifest_address"}, "decision manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 2 or tuple(manifest["files"]) != FILES:
        raise ValidationError("decision manifest contract is invalid")
    if manifest["manifest_address"] != _manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("decision manifest address mismatch")
    if len(manifest["artifacts"]) != 2:
        raise ValidationError("decision manifest artifact count is invalid")
    _check_artifact(manifest, source / LEDGER_NAME, LEDGER_NAME)
    _check_artifact(manifest, source / ENTRIES_NAME, ENTRIES_NAME)
    ledger_document = _read_json(source / LEDGER_NAME, "decision ledger")
    _strict(ledger_document, {"ledger_id", "version", "boundary", "federation_id", "queue_id", "queue_address", "queue_state", "gate_state", "queue_release_ready", "item_count", "entry_count", "covered_count", "open_count", "closed_count", "unreviewed_count", "escalated_count", "blocked_count", "state", "accepted", "release_ready", "items", "head_address", "content_address"}, "decision ledger")
    entries_document = _read_json(source / ENTRIES_NAME, "decision entries")
    _strict(entries_document, {"version", "boundary", "ledger_id", "ledger_address", "entry_count", "entries_address", "entries"}, "decision entries")
    if entries_document["version"] != VERSION or entries_document["boundary"] != BOUNDARY or entries_document["ledger_id"] != ledger_document["ledger_id"] or entries_document["ledger_address"] != ledger_document["content_address"]:
        raise ValidationError("decision entries linkage is invalid")
    entries = tuple(decision_entry_from_mapping(item) for item in _mapping_sequence(entries_document["entries"], "decision entries"))
    if entries_document["entry_count"] != len(entries) or entries_document["entries_address"] != content_hash({"ledger_id": entries_document["ledger_id"], "entries": [entry.to_dict() for entry in entries]}, prefix=ENTRIES_PREFIX):
        raise ValidationError("decision entries address is invalid")
    body = dict(ledger_document)
    items = tuple(review_model.federation_review_item_from_mapping(item) for item in _mapping_sequence(body.pop("items"), "decision items"))
    value = FederationReviewDecisionLedger(**body, items=items, entries=entries)
    if manifest["ledger_id"] != value.ledger_id or manifest["queue_id"] != value.queue_id or manifest["queue_address"] != value.queue_address or manifest["ledger_address"] != value.content_address or manifest["entry_address"] != address_decision_entries(value):
        raise ValidationError("decision manifest linkage is invalid")
    return verify_decision_ledger(value)


def decision_ledger_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Review Decision Ledger", "type": "object", "additionalProperties": False, "properties": {"ledger_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "queue_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "open_count": {"type": "integer", "minimum": 0}, "closed_count": {"type": "integer", "minimum": 0}, "state": {"enum": [item.value for item in DecisionLedgerState]}, "release_ready": {"type": "boolean"}, "items": {"type": "array"}, "entries": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["ledger_id", "version", "boundary", "queue_address", "entry_count", "state", "release_ready", "content_address"]}


def decision_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Review Decision Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": ["summary", "entries", "items", "open", "closed", "escalated", "blockers", "added", "removed", "changed", "unchanged", "resolved"]}, "state": {"type": ["string", "null"]}, "action": {"type": ["string", "null"]}, "record_type": {"type": ["string", "null"]}, "plane": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}, "required": ["resource", "offset", "limit"]}


def decision_diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Review Decision Diff", "type": "object", "additionalProperties": False, "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "baseline_ledger_address": {"type": "string"}, "candidate_ledger_address": {"type": "string"}, "state": {"enum": ["improved", "regressed", "changed", "unchanged"]}, "item_count": {"type": "integer", "minimum": 0}, "resolved_count": {"type": "integer", "minimum": 0}, "items": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["diff_id", "version", "boundary", "baseline_ledger_address", "candidate_ledger_address", "state", "item_count", "content_address"]}


def decision_capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "actions": [item.value for item in DecisionAction], "results": [item.value for item in DecisionResult], "states": [item.value for item in DecisionLedgerState], "diff_actions": [item.value for item in DecisionDiffAction], "limits": {"items": MAX_ITEMS, "entries": MAX_ENTRIES, "query_items": MAX_QUERY_ITEMS}, "persistence": {"files": list(FILES), "atomic_write": True, "canonical_json": True, "head_guard": True}, "rules": {"remediate_requires_evidence": True, "critical_waiver": False, "source_gate_remains_authoritative": True, "reopen_requires_prior_decision": True}, "queries": {"resources": ["summary", "entries", "items", "open", "closed", "escalated", "blockers", "added", "removed", "changed", "unchanged", "resolved"], "pagination": True, "filters": ["state", "action", "record_type", "plane", "text"]}, "diff": {"state_values": ["improved", "regressed", "changed", "unchanged"], "resolved_transition": "open-to-closed"}}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LEDGER_ID",
    "DecisionAction",
    "DecisionDiffAction",
    "DecisionLedgerState",
    "DecisionQuery",
    "DecisionQueryResult",
    "DecisionResult",
    "ENTRIES_NAME",
    "FILES",
    "FederationReviewDecisionEntry",
    "FederationReviewDecisionDiff",
    "FederationReviewDecisionDiffItem",
    "FederationReviewDecisionLedger",
    "address_decision_diff",
    "address_decision_diff_item",
    "address_decision_entries",
    "address_decision_entry",
    "address_decision_item",
    "address_decision_ledger",
    "append_decision",
    "append_decision_by_address",
    "build_decision_ledger",
    "build_decision_diff",
    "decision_capabilities",
    "decision_entry_from_mapping",
    "decision_ledger_csv",
    "decision_ledger_from_mapping",
    "decision_ledger_json",
    "decision_ledger_schema",
    "decision_diff_csv",
    "decision_diff_from_mapping",
    "decision_diff_item_from_mapping",
    "decision_diff_json",
    "decision_diff_schema",
    "decision_query_csv",
    "decision_query_json",
    "decision_query_schema",
    "load_decision_ledger",
    "query_decision_diff",
    "query_decision_ledger",
    "render_decision_diff_markdown",
    "render_decision_ledger_markdown",
    "render_decision_query_markdown",
    "verify_decision_ledger",
    "write_decision_ledger",
]
