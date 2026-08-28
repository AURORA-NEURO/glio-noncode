"""Route federation assurance findings into a durable review queue.

The assurance gate answers whether a federation can be promoted.  This module
answers the operational follow-up questions: which findings need review,
which blockers are critical, what remediation text is attached to each item,
and how a candidate gate differs from a baseline gate.

The review projection contains no source paths, identities, or scientific
payloads.  It preserves only addressed component links, fixed-vocabulary
states, bounded remediation text, and deterministic comparison records.  A
queue can be moved independently as a two-file package and queried offline.
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
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate as gate_model,
)
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

FederationReleaseGate = gate_model.FederationReleaseGate
FederationAssurance = gate_model.FederationAssurance
VERSION = gate_model.VERSION + "-review-v1"
BOUNDARY = "public_registry_federation_assurance_gate_review"
REVIEW_PREFIX = gate_model.GATE_PREFIX + "-review"
ITEM_PREFIX = REVIEW_PREFIX + "-item"
DIFF_PREFIX = REVIEW_PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
MANIFEST_PREFIX = REVIEW_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
REVIEW_NAME = "review.json"
FILES = (MANIFEST_NAME, REVIEW_NAME)
MAX_ITEMS = 128
MAX_DIFF_ITEMS = 256
MAX_QUERY_ITEMS = 4096
DEFAULT_LIMIT = 50

_FORBIDDEN_KEYS = frozenset({"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"})


class ReviewState(StrEnum):
    CLEAR = "clear"
    REVIEW = "review"
    BLOCKED = "blocked"


class ReviewPriority(StrEnum):
    NONE = "none"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewRecordType(StrEnum):
    FINDING = "finding"
    CHECK = "check"


class DiffAction(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be an address")
    return value


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


def _json_value(value: Any, field: str) -> Any:
    try:
        encoded = canonical_bytes(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be JSON-compatible") from exc
    if len(encoded) > 1_000_000:
        raise ValidationError(f"{field} is too large")
    return value


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in _FORBIDDEN_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) - allowed:
        raise ValidationError(f"{field} contains unknown fields")


def _file_address(name: str, raw: bytes) -> str:
    return hash_bytes(raw, prefix=f"{MANIFEST_PREFIX}:{name.removesuffix('.json')}")


def _remediation_state(passed: bool, severity: str, required: bool | None) -> tuple[str, str]:
    if passed:
        return ReviewState.CLEAR.value, ReviewPriority.NONE.value
    if severity == "blocker" or required is True:
        return ReviewState.BLOCKED.value, ReviewPriority.CRITICAL.value
    return ReviewState.REVIEW.value, ReviewPriority.HIGH.value


def address_review_item(value: FederationReviewItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class FederationReviewItem:
    """One actionable or cleared assurance/gate record."""

    def __init__(
        self,
        ordinal: int,
        record_type: str,
        record_id: str,
        plane: str,
        kind: str,
        severity: str,
        required: bool | None,
        passed: bool,
        state: str,
        priority: str,
        remediation: str,
        evidence_address: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.record_type = record_type
        self.record_id = record_id
        self.plane = plane
        self.kind = kind
        self.severity = severity
        self.required = required
        self.passed = passed
        self.state = state
        self.priority = priority
        self.remediation = remediation
        self.evidence_address = evidence_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "review item ordinal", MAX_ITEMS)
        if self.record_type not in {item.value for item in ReviewRecordType}:
            raise ValidationError("review item record type is invalid")
        _text(self.record_id, "review item record ID", 512)
        _text(self.plane, "review item plane", 64)
        _text(self.kind, "review item kind", 256)
        if self.severity not in {"pass", "warning", "blocker"}:
            raise ValidationError("review item severity is invalid")
        if self.required is not None:
            _bool(self.required, "review item required flag")
        _bool(self.passed, "review item passed flag")
        if self.state not in {item.value for item in ReviewState}:
            raise ValidationError("review item state is invalid")
        if self.priority not in {item.value for item in ReviewPriority}:
            raise ValidationError("review item priority is invalid")
        _text(self.remediation, "review item remediation")
        _address(self.evidence_address, "review item evidence address")
        _address(self.content_address, "review item address")
        expected_state, expected_priority = _remediation_state(self.passed, self.severity, self.required)
        if (self.state, self.priority) != (expected_state, expected_priority):
            raise ValidationError("review item state does not follow evidence")
        if self.passed and self.severity != "pass":
            raise ValidationError("passed review items must have pass severity")
        if not self.passed and self.severity == "pass":
            raise ValidationError("failed review items cannot have pass severity")
        if not _public(self.to_dict()):
            raise ValidationError("review item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "record_type": self.record_type, "record_id": self.record_id, "plane": self.plane, "kind": self.kind, "severity": self.severity, "required": self.required, "passed": self.passed, "state": self.state, "priority": self.priority, "remediation": self.remediation, "evidence_address": self.evidence_address, "content_address": self.content_address}


def _make_item(ordinal: int, record_type: str, source: Any) -> FederationReviewItem:
    required = getattr(source, "required", None)
    passed = bool(source.passed)
    severity = str(source.severity)
    state, priority = _remediation_state(passed, severity, required)
    body = {"ordinal": ordinal, "record_type": record_type, "record_id": getattr(source, "finding_id", getattr(source, "check_id", "")), "plane": source.plane, "kind": source.kind, "severity": severity, "required": required, "passed": passed, "state": state, "priority": priority, "remediation": source.remediation, "evidence_address": source.content_address}
    provisional = FederationReviewItem(**body, content_address="pending:item")
    return FederationReviewItem(**body, content_address=address_review_item(provisional))


def address_review_queue(value: FederationReviewQueue) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REVIEW_PREFIX)


class FederationReviewQueue:
    """Conserved remediation routing for one assurance gate."""

    def __init__(
        self,
        queue_id: str,
        version: str,
        boundary: str,
        federation_id: str,
        gate_address: str,
        assurance_address: str,
        gate_state: str,
        release_ready: bool,
        item_count: int,
        clear_count: int,
        warning_count: int,
        blocker_count: int,
        open_count: int,
        critical_count: int,
        state: str,
        accepted: bool,
        items: Sequence[FederationReviewItem],
        content_address: str,
    ) -> None:
        self.queue_id = queue_id
        self.version = version
        self.boundary = boundary
        self.federation_id = federation_id
        self.gate_address = gate_address
        self.assurance_address = assurance_address
        self.gate_state = gate_state
        self.release_ready = release_ready
        self.item_count = item_count
        self.clear_count = clear_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.open_count = open_count
        self.critical_count = critical_count
        self.state = state
        self.accepted = accepted
        self.items = tuple(items)
        self.content_address = content_address
        self.gate: FederationReleaseGate | None = None
        self.assurance: FederationAssurance | None = None
        self._validate()

    def _validate(self) -> None:
        _text(self.queue_id, "review queue ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("review queue contract is invalid")
        _text(self.federation_id, "review federation ID", 256)
        _address(self.gate_address, "review gate address")
        _address(self.assurance_address, "review assurance address")
        if self.gate_state not in {"promote", "hold", "block"}:
            raise ValidationError("review gate state is invalid")
        _bool(self.release_ready, "review release-ready flag")
        _count(self.item_count, "review item count", MAX_ITEMS, positive=True)
        for count, field in ((self.clear_count, "clear count"), (self.warning_count, "warning count"), (self.blocker_count, "blocker count"), (self.open_count, "open count"), (self.critical_count, "critical count")):
            _count(count, f"review {field}", MAX_ITEMS)
        if self.item_count != len(self.items) or self.item_count == 0:
            raise ValidationError("review item count is not conserved")
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, FederationReviewItem) or item.ordinal != ordinal:
                raise ValidationError("review item ordinals are not contiguous")
            if address_review_item(item) != item.content_address:
                raise ValidationError("review item address mismatch")
        counts = {
            "clear": sum(item.state == ReviewState.CLEAR.value for item in self.items),
            "warning": sum(item.state == ReviewState.REVIEW.value for item in self.items),
            "blocker": sum(item.state == ReviewState.BLOCKED.value for item in self.items),
            "open": sum(item.state != ReviewState.CLEAR.value for item in self.items),
            "critical": sum(item.priority == ReviewPriority.CRITICAL.value for item in self.items),
        }
        if (self.clear_count, self.warning_count, self.blocker_count, self.open_count, self.critical_count) != tuple(counts[item] for item in ("clear", "warning", "blocker", "open", "critical")):
            raise ValidationError("review state counts are not conserved")
        expected_state = "blocked" if self.blocker_count else "review" if self.warning_count else "clear"
        if self.state != expected_state:
            raise ValidationError("review queue state is invalid")
        if self.accepted != (self.blocker_count == 0):
            raise ValidationError("review queue acceptance is invalid")
        if self.release_ready != (self.state == ReviewState.CLEAR.value):
            raise ValidationError("review queue readiness is invalid")
        _address(self.content_address, "review queue address")
        if not _public(self.to_dict()):
            raise ValidationError("review queue crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"queue_id": self.queue_id, "version": self.version, "boundary": self.boundary, "federation_id": self.federation_id, "gate_address": self.gate_address, "assurance_address": self.assurance_address, "gate_state": self.gate_state, "release_ready": self.release_ready, "item_count": self.item_count, "clear_count": self.clear_count, "warning_count": self.warning_count, "blocker_count": self.blocker_count, "open_count": self.open_count, "critical_count": self.critical_count, "state": self.state, "accepted": self.accepted, "content_address": self.content_address}

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def build_review_queue(gate: FederationReleaseGate, *, queue_id: str = "glio-noncode-observatory-registry-federation-review-queue") -> FederationReviewQueue:
    if not isinstance(gate, FederationReleaseGate):
        raise ValidationError("review queue requires a typed release gate")
    gate_model.verify_federation_assurance_gate(gate)
    sources = tuple(_make_item(index, ReviewRecordType.FINDING.value, finding) for index, finding in enumerate(gate.assurance.findings)) + tuple(_make_item(index + len(gate.assurance.findings), ReviewRecordType.CHECK.value, check) for index, check in enumerate(gate.checks))
    body = {"queue_id": _text(queue_id, "review queue ID", 256), "version": VERSION, "boundary": BOUNDARY, "federation_id": gate.federation_id, "gate_address": gate.content_address, "assurance_address": gate.assurance_address, "gate_state": gate.state, "release_ready": gate.release_ready, "item_count": len(sources), "clear_count": sum(item.state == "clear" for item in sources), "warning_count": sum(item.state == "review" for item in sources), "blocker_count": sum(item.state == "blocked" for item in sources), "open_count": sum(item.state != "clear" for item in sources), "critical_count": sum(item.priority == "critical" for item in sources), "state": "blocked" if any(item.state == "blocked" for item in sources) else "review" if any(item.state == "review" for item in sources) else "clear", "accepted": not any(item.state == "blocked" for item in sources), "items": sources}
    provisional = FederationReviewQueue(**body, content_address="pending:queue")
    queue = FederationReviewQueue(**body, content_address=address_review_queue(provisional))
    queue.gate = gate
    queue.assurance = gate.assurance
    return queue


def build_review_queue_from_directory(directory: str | Path, *, queue_id: str = "glio-noncode-observatory-registry-federation-review-queue") -> FederationReviewQueue:
    return build_review_queue(gate_model.load_federation_assurance_gate(directory), queue_id=queue_id)


def verify_review_queue(value: FederationReviewQueue) -> FederationReviewQueue:
    if not isinstance(value, FederationReviewQueue):
        raise ValidationError("review verification requires a typed queue")
    for item in value.items:
        if address_review_item(item) != item.content_address:
            raise ValidationError("review item address mismatch")
    if address_review_queue(value) != value.content_address:
        raise ValidationError("review queue address mismatch")
    return value


def _item_key(item: FederationReviewItem) -> tuple[str, str, str]:
    return item.record_type, item.plane, item.kind


def address_review_diff_item(value: FederationReviewDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


class FederationReviewDiffItem:
    def __init__(self, ordinal: int, action: str, key: str, record_type: str, plane: str, kind: str, baseline_state: str | None, candidate_state: str | None, baseline_priority: str | None, candidate_priority: str | None, baseline_address: str | None, candidate_address: str | None, remediation: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.action = action
        self.key = key
        self.record_type = record_type
        self.plane = plane
        self.kind = kind
        self.baseline_state = baseline_state
        self.candidate_state = candidate_state
        self.baseline_priority = baseline_priority
        self.candidate_priority = candidate_priority
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "diff item ordinal", MAX_DIFF_ITEMS)
        if self.action not in {item.value for item in DiffAction}:
            raise ValidationError("diff action is invalid")
        _text(self.key, "diff item key", 512)
        if self.record_type not in {item.value for item in ReviewRecordType}:
            raise ValidationError("diff record type is invalid")
        _text(self.plane, "diff plane", 64)
        _text(self.kind, "diff kind", 256)
        for value, field in ((self.baseline_state, "baseline state"), (self.candidate_state, "candidate state"), (self.baseline_priority, "baseline priority"), (self.candidate_priority, "candidate priority")):
            if value is not None:
                _text(value, field, 64)
        for value, field in ((self.baseline_address, "baseline item address"), (self.candidate_address, "candidate item address")):
            if value is not None:
                _address(value, field)
        _text(self.remediation, "diff remediation")
        _address(self.content_address, "diff item address")
        if self.action == "added" and self.candidate_state is None:
            raise ValidationError("added diff item requires a candidate")
        if self.action == "removed" and self.baseline_state is None:
            raise ValidationError("removed diff item requires a baseline")
        if self.action in {"unchanged", "changed"} and (self.baseline_state is None or self.candidate_state is None):
            raise ValidationError("matched diff item requires both snapshots")
        if not _public(self.to_dict()):
            raise ValidationError("diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "action": self.action, "key": self.key, "record_type": self.record_type, "plane": self.plane, "kind": self.kind, "baseline_state": self.baseline_state, "candidate_state": self.candidate_state, "baseline_priority": self.baseline_priority, "candidate_priority": self.candidate_priority, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "remediation": self.remediation, "content_address": self.content_address}


def _make_diff_item(ordinal: int, action: str, baseline: FederationReviewItem | None, candidate: FederationReviewItem | None) -> FederationReviewDiffItem:
    source = candidate or baseline
    key = ":".join(_item_key(source))
    changed = baseline is not None and candidate is not None and (baseline.state != candidate.state or baseline.priority != candidate.priority or baseline.remediation != candidate.remediation)
    resolved_action = DiffAction.CHANGED.value if action == DiffAction.UNCHANGED.value and changed else action
    body = {"ordinal": ordinal, "action": resolved_action, "key": key, "record_type": source.record_type, "plane": source.plane, "kind": source.kind, "baseline_state": baseline.state if baseline else None, "candidate_state": candidate.state if candidate else None, "baseline_priority": baseline.priority if baseline else None, "candidate_priority": candidate.priority if candidate else None, "baseline_address": baseline.content_address if baseline else None, "candidate_address": candidate.content_address if candidate else None, "remediation": (candidate or baseline).remediation}
    provisional = FederationReviewDiffItem(**body, content_address="pending:diff-item")
    return FederationReviewDiffItem(**body, content_address=address_review_diff_item(provisional))


def address_review_diff(value: FederationReviewDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


class FederationReviewDiff:
    def __init__(self, diff_id: str, version: str, boundary: str, federation_id: str, baseline_queue_address: str, candidate_queue_address: str, baseline_state: str, candidate_state: str, item_count: int, added_count: int, removed_count: int, unchanged_count: int, changed_count: int, resolved_count: int, state: str, items: Sequence[FederationReviewDiffItem], content_address: str) -> None:
        self.diff_id = diff_id
        self.version = version
        self.boundary = boundary
        self.federation_id = federation_id
        self.baseline_queue_address = baseline_queue_address
        self.candidate_queue_address = candidate_queue_address
        self.baseline_state = baseline_state
        self.candidate_state = candidate_state
        self.item_count = item_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.resolved_count = resolved_count
        self.state = state
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "review diff ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("review diff contract is invalid")
        _text(self.federation_id, "diff federation ID", 256)
        _address(self.baseline_queue_address, "baseline queue address")
        _address(self.candidate_queue_address, "candidate queue address")
        for value, field in ((self.baseline_state, "baseline state"), (self.candidate_state, "candidate state")):
            _text(value, field, 64)
        _count(self.item_count, "diff item count", MAX_DIFF_ITEMS)
        for count, field in ((self.added_count, "added count"), (self.removed_count, "removed count"), (self.unchanged_count, "unchanged count"), (self.changed_count, "changed count"), (self.resolved_count, "resolved count")):
            _count(count, f"diff {field}", MAX_DIFF_ITEMS)
        if self.item_count != len(self.items):
            raise ValidationError("diff item count is not conserved")
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, FederationReviewDiffItem) or item.ordinal != ordinal:
                raise ValidationError("diff item ordinals are not contiguous")
            if address_review_diff_item(item) != item.content_address:
                raise ValidationError("diff item address mismatch")
        counts = {action.value: sum(item.action == action.value for item in self.items) for action in DiffAction}
        if (self.added_count, self.removed_count, self.unchanged_count, self.changed_count) != tuple(counts[item] for item in ("added", "removed", "unchanged", "changed")):
            raise ValidationError("diff action counts are not conserved")
        resolved = sum(item.baseline_state in {"review", "blocked"} and item.candidate_state == "clear" for item in self.items)
        if self.resolved_count != resolved:
            raise ValidationError("diff resolved count is not conserved")
        if self.state not in {"unchanged", "changed", "improved", "regressed"}:
            raise ValidationError("diff state is invalid")
        _address(self.content_address, "review diff address")
        if not _public(self.to_dict()):
            raise ValidationError("review diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "federation_id": self.federation_id, "baseline_queue_address": self.baseline_queue_address, "candidate_queue_address": self.candidate_queue_address, "baseline_state": self.baseline_state, "candidate_state": self.candidate_state, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "resolved_count": self.resolved_count, "state": self.state, "content_address": self.content_address}

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def build_review_diff(baseline: FederationReviewQueue, candidate: FederationReviewQueue, *, diff_id: str = "glio-noncode-observatory-registry-federation-review-diff") -> FederationReviewDiff:
    verify_review_queue(baseline)
    verify_review_queue(candidate)
    baseline_by_key = {_item_key(item): item for item in baseline.items}
    candidate_by_key = {_item_key(item): item for item in candidate.items}
    keys = sorted(set(baseline_by_key) | set(candidate_by_key))
    items = tuple(_make_diff_item(index, "added" if key not in baseline_by_key else "removed" if key not in candidate_by_key else "unchanged", baseline_by_key.get(key), candidate_by_key.get(key)) for index, key in enumerate(keys))
    candidate_open = candidate.warning_count + candidate.blocker_count
    baseline_open = baseline.warning_count + baseline.blocker_count
    state = "improved" if candidate_open < baseline_open else "regressed" if candidate_open > baseline_open else "unchanged"
    if candidate.state != baseline.state and candidate_open == baseline_open:
        state = "changed"
    body = {"diff_id": _text(diff_id, "review diff ID", 256), "version": VERSION, "boundary": BOUNDARY, "federation_id": candidate.federation_id, "baseline_queue_address": baseline.content_address, "candidate_queue_address": candidate.content_address, "baseline_state": baseline.state, "candidate_state": candidate.state, "item_count": len(items), "added_count": sum(item.action == "added" for item in items), "removed_count": sum(item.action == "removed" for item in items), "unchanged_count": sum(item.action == "unchanged" for item in items), "changed_count": sum(item.action == "changed" for item in items), "resolved_count": sum(item.baseline_state in {"review", "blocked"} and item.candidate_state == "clear" for item in items), "state": state, "items": items}
    provisional = FederationReviewDiff(**body, content_address="pending:diff")
    return FederationReviewDiff(**body, content_address=address_review_diff(provisional))


def verify_review_diff(value: FederationReviewDiff) -> FederationReviewDiff:
    if not isinstance(value, FederationReviewDiff):
        raise ValidationError("diff verification requires a typed diff")
    for item in value.items:
        if address_review_diff_item(item) != item.content_address:
            raise ValidationError("diff item address mismatch")
    if address_review_diff(value) != value.content_address:
        raise ValidationError("review diff address mismatch")
    return value


def federation_review_item_from_mapping(value: Mapping[str, Any]) -> FederationReviewItem:
    value = _mapping(value, "review item")
    _strict(value, {"ordinal", "record_type", "record_id", "plane", "kind", "severity", "required", "passed", "state", "priority", "remediation", "evidence_address", "content_address"}, "review item")
    return FederationReviewItem(**dict(value))


def review_queue_from_mapping(value: Mapping[str, Any]) -> FederationReviewQueue:
    value = _mapping(value, "review queue")
    _strict(value, {"queue_id", "version", "boundary", "federation_id", "gate_address", "assurance_address", "gate_state", "release_ready", "item_count", "clear_count", "warning_count", "blocker_count", "open_count", "critical_count", "state", "accepted", "items", "content_address"}, "review queue")
    items = value.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ValidationError("review queue items must be an array")
    body = dict(value)
    body["items"] = tuple(federation_review_item_from_mapping(item) for item in items)
    return verify_review_queue(FederationReviewQueue(**body))


def federation_review_diff_item_from_mapping(value: Mapping[str, Any]) -> FederationReviewDiffItem:
    value = _mapping(value, "review diff item")
    _strict(value, {"ordinal", "action", "key", "record_type", "plane", "kind", "baseline_state", "candidate_state", "baseline_priority", "candidate_priority", "baseline_address", "candidate_address", "remediation", "content_address"}, "review diff item")
    return FederationReviewDiffItem(**dict(value))


def review_diff_from_mapping(value: Mapping[str, Any]) -> FederationReviewDiff:
    value = _mapping(value, "review diff")
    _strict(value, {"diff_id", "version", "boundary", "federation_id", "baseline_queue_address", "candidate_queue_address", "baseline_state", "candidate_state", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "resolved_count", "state", "items", "content_address"}, "review diff")
    items = value.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ValidationError("review diff items must be an array")
    body = dict(value)
    body["items"] = tuple(federation_review_diff_item_from_mapping(item) for item in items)
    return verify_review_diff(FederationReviewDiff(**body))


def review_queue_json(value: FederationReviewQueue) -> str:
    verify_review_queue(value)
    return canonical_json(value.to_dict())


def review_diff_json(value: FederationReviewDiff) -> str:
    verify_review_diff(value)
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    return stream.getvalue()


def review_queue_csv(value: FederationReviewQueue) -> str:
    verify_review_queue(value)
    fields = ("ordinal", "record_type", "record_id", "plane", "kind", "severity", "required", "passed", "state", "priority", "remediation", "evidence_address", "content_address")
    return _csv_text([item.to_dict() for item in value.items], fields)


def review_diff_csv(value: FederationReviewDiff) -> str:
    verify_review_diff(value)
    fields = ("ordinal", "action", "key", "record_type", "plane", "kind", "baseline_state", "candidate_state", "baseline_priority", "candidate_priority", "remediation", "content_address")
    return _csv_text([item.to_dict() for item in value.items], fields)


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", ""]
    lines.extend(f"- {key.replace('_', ' ').title()}: `{value}`" for key, value in summary.items() if key not in {"content_address", "version", "boundary"})
    lines.append("")
    if not rows:
        lines.extend(["No records.", ""])
        return "\n".join(lines)
    fields = sorted({key for row in rows for key in row})
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("|" + "|".join("---" for _ in fields) + "|")
    lines.extend("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def render_review_queue_markdown(value: FederationReviewQueue) -> str:
    verify_review_queue(value)
    return _markdown("Observatory Packet Registry Federation Review Queue", value.summary(), [item.to_dict() for item in value.items])


def render_review_diff_markdown(value: FederationReviewDiff) -> str:
    verify_review_diff(value)
    return _markdown("Observatory Packet Registry Federation Review Diff", value.summary(), [item.to_dict() for item in value.items])


class ReviewQuery:
    def __init__(self, resource: str = "summary", *, state: str | None = None, priority: str | None = None, action: str | None = None, passed: bool | None = None, record_type: str | None = None, plane: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "review query resource", 64)
        if self.resource not in {"summary", "items", "open", "blockers", "warnings", "clear", "added", "removed", "changed", "unchanged", "resolved"}:
            raise ValidationError("review query resource is invalid")
        if state is not None and state not in {item.value for item in ReviewState}:
            raise ValidationError("review query state is invalid")
        if priority is not None and priority not in {item.value for item in ReviewPriority}:
            raise ValidationError("review query priority is invalid")
        if action is not None and action not in {item.value for item in DiffAction}:
            raise ValidationError("review query action is invalid")
        if passed is not None:
            _bool(passed, "review query passed")
        if record_type is not None and record_type not in {item.value for item in ReviewRecordType}:
            raise ValidationError("review query record type is invalid")
        self.state = state
        self.priority = priority
        self.action = action
        self.passed = passed
        self.record_type = record_type
        self.plane = _text(plane, "review query plane", 64) if plane is not None else None
        self.text = _text(text, "review query text", 256).casefold() if text is not None else None
        self.offset = _count(offset, "review query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "review query limit", MAX_QUERY_ITEMS, positive=True)
        if self.offset + self.limit > MAX_QUERY_ITEMS:
            raise ValidationError("review query window is too large")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "state": self.state, "priority": self.priority, "action": self.action, "passed": self.passed, "record_type": self.record_type, "plane": self.plane, "text": self.text, "offset": self.offset, "limit": self.limit}


def address_review_query(value: ReviewQuery) -> str:
    return content_hash(value.to_dict(), prefix=REVIEW_PREFIX + "-query")


class ReviewQueryResult:
    def __init__(self, query: ReviewQuery, total_count: int, items: Sequence[Mapping[str, Any]], source_address: str) -> None:
        self.query = query
        self.total_count = total_count
        self.items = tuple(dict(item) for item in items)
        self.returned_count = len(self.items)
        self.source_address = source_address
        self.content_address = "pending:query"
        self.content_address = content_hash(self.to_dict() | {"content_address": None}, prefix=REVIEW_PREFIX + "-query-result")
        self._validate()

    def _validate(self) -> None:
        _count(self.total_count, "query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count:
            raise ValidationError("query returned count exceeds total")
        _address(self.source_address, "query source address")
        if not _public(self.to_dict()):
            raise ValidationError("review query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "source_address": self.source_address, "content_address": self.content_address}


def _matches(item: Mapping[str, Any], query: ReviewQuery) -> bool:
    if query.state is not None and item.get("state", item.get("candidate_state")) != query.state:
        return False
    if query.priority is not None and item.get("priority", item.get("candidate_priority")) != query.priority:
        return False
    if query.action is not None and item.get("action") != query.action:
        return False
    if query.passed is not None and item.get("passed") != query.passed:
        return False
    if query.record_type is not None and item.get("record_type") != query.record_type:
        return False
    if query.plane is not None and item.get("plane") != query.plane:
        return False
    if query.text is not None and query.text not in canonical_json(item).casefold():
        return False
    return True


def query_review_queue(value: FederationReviewQueue, query: ReviewQuery | None = None, **kwargs: Any) -> ReviewQueryResult:
    verify_review_queue(value)
    selected = query if query is not None else ReviewQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    if selected.resource == "summary":
        items = (value.summary(),)
    else:
        items = [item.to_dict() for item in value.items]
        if selected.resource == "open":
            items = [item for item in items if item["state"] != "clear"]
        elif selected.resource == "blockers":
            items = [item for item in items if item["state"] == "blocked"]
        elif selected.resource == "warnings":
            items = [item for item in items if item["state"] == "review"]
        elif selected.resource == "clear":
            items = [item for item in items if item["state"] == "clear"]
    matched = tuple(item for item in items if _matches(item, selected))
    return ReviewQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], value.content_address)


def query_review_diff(value: FederationReviewDiff, query: ReviewQuery | None = None, **kwargs: Any) -> ReviewQueryResult:
    verify_review_diff(value)
    selected = query if query is not None else ReviewQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    if selected.resource == "summary":
        items = (value.summary(),)
    else:
        items = [item.to_dict() for item in value.items]
        if selected.resource in {"added", "removed", "changed", "unchanged", "resolved"}:
            items = [item for item in items if item["action"] == selected.resource or selected.resource == "resolved" and item["baseline_state"] in {"review", "blocked"} and item["candidate_state"] == "clear"]
    matched = tuple(item for item in items if _matches(item, selected))
    return ReviewQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], value.content_address)


def review_query_json(value: ReviewQueryResult) -> str:
    return canonical_json(value.to_dict())


def review_query_csv(value: ReviewQueryResult) -> str:
    if not value.items:
        return ""
    fields = sorted({key for item in value.items for key in item})
    return _csv_text(value.items, fields)


def render_review_query_markdown(value: ReviewQueryResult) -> str:
    return _markdown("Observatory Packet Registry Federation Review Query", {"resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def _manifest_body(value: FederationReviewQueue, raw: bytes) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "queue_id": value.queue_id, "federation_id": value.federation_id, "queue_address": value.content_address, "artifact_count": 1, "files": list(FILES), "artifact": {"name": REVIEW_NAME, "bytes": len(raw), "byte_address": hash_bytes(raw), "file_address": _file_address(REVIEW_NAME, raw)}, "manifest_address": None}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=MANIFEST_PREFIX)


def write_review_queue(value: FederationReviewQueue, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_review_queue(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("review queue destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(value.to_dict())
    manifest_body = _manifest_body(value, raw)
    manifest_body["manifest_address"] = _manifest_address(manifest_body)
    manifest = canonical_bytes(manifest_body)
    temporary = Path(tempfile.mkdtemp(prefix=f".{REVIEW_PREFIX}-", dir=str(destination.parent)))
    try:
        (temporary / REVIEW_NAME).write_bytes(raw)
        (temporary / MANIFEST_NAME).write_bytes(manifest)
        if destination.exists():
            if not destination.is_dir() or any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("review queue destination already exists")
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


def load_review_queue(directory: str | Path) -> FederationReviewQueue:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("review queue input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(FILES):
        raise ValidationError("review queue file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "review manifest")
    _strict(manifest, {"version", "boundary", "queue_id", "federation_id", "queue_address", "artifact_count", "files", "artifact", "manifest_address"}, "review manifest")
    actual = manifest["manifest_address"]
    expected = dict(manifest)
    expected["manifest_address"] = None
    if actual != _manifest_address(expected):
        raise ValidationError("review manifest address mismatch")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["files"] != list(FILES) or manifest["artifact_count"] != 1:
        raise ValidationError("review manifest metadata is invalid")
    artifact = _mapping(manifest["artifact"], "review artifact")
    _strict(artifact, {"name", "bytes", "byte_address", "file_address"}, "review artifact")
    raw = (source / REVIEW_NAME).read_bytes()
    if artifact["name"] != REVIEW_NAME or artifact["bytes"] != len(raw) or artifact["byte_address"] != hash_bytes(raw) or artifact["file_address"] != _file_address(REVIEW_NAME, raw):
        raise ValidationError("review artifact address mismatch")
    queue = review_queue_from_mapping(_read_json(source / REVIEW_NAME, "review queue"))
    if queue.content_address != manifest["queue_address"] or queue.queue_id != manifest["queue_id"]:
        raise ValidationError("review manifest linkage mismatch")
    return verify_review_queue(queue)


def review_queue_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Review Queue", "type": "object", "additionalProperties": False, "required": ["queue_id", "version", "boundary", "federation_id", "gate_address", "assurance_address", "item_count", "items", "state", "accepted", "content_address"], "properties": {"queue_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "federation_id": {"type": "string"}, "gate_address": {"type": "string"}, "assurance_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 1}, "items": {"type": "array"}, "state": {"enum": [item.value for item in ReviewState]}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def review_diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Review Diff", "type": "object", "additionalProperties": False, "required": ["diff_id", "version", "boundary", "federation_id", "baseline_queue_address", "candidate_queue_address", "item_count", "items", "state", "content_address"], "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "federation_id": {"type": "string"}, "baseline_queue_address": {"type": "string"}, "candidate_queue_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0}, "items": {"type": "array"}, "state": {"enum": ["unchanged", "changed", "improved", "regressed"]}, "content_address": {"type": "string"}}}


def review_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Review Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": ["summary", "items", "open", "blockers", "warnings", "clear", "added", "removed", "changed", "unchanged", "resolved"]}, "state": {"type": ["string", "null"]}, "priority": {"type": ["string", "null"]}, "action": {"type": ["string", "null"]}, "passed": {"type": ["boolean", "null"]}, "record_type": {"type": ["string", "null"]}, "plane": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}}


def review_capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "queue": {"item_count": 36, "states": [item.value for item in ReviewState], "priorities": [item.value for item in ReviewPriority], "record_types": [item.value for item in ReviewRecordType]}, "diff": {"actions": [item.value for item in DiffAction], "states": ["unchanged", "changed", "improved", "regressed"]}, "persistence": {"exact_files": list(FILES), "canonical_json": True, "atomic_write": True, "symlink_rejected": True, "offline_load": True}, "queries": {"pagination": True, "state_filter": True, "priority_filter": True, "action_filter": True, "text_filter": True, "csv": True, "markdown": True}, "public_boundary": {"path_free": True, "forbidden_keys": sorted(_FORBIDDEN_KEYS)}}


# Long aliases keep the repository's public module naming convention intact.
build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review = build_review_queue
build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_from_directory = build_review_queue_from_directory
build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_diff = build_review_diff
load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review = load_review_queue
write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review = write_review_queue
verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review = verify_review_queue
verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_diff = verify_review_diff
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_schema = review_queue_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_diff_schema = review_diff_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_query_schema = review_query_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_capabilities = review_capabilities


__all__ = [
    "DiffAction",
    "FederationReviewDiff",
    "FederationReviewDiffItem",
    "FederationReviewItem",
    "FederationReviewQueue",
    "ReviewPriority",
    "ReviewQuery",
    "ReviewQueryResult",
    "ReviewRecordType",
    "ReviewState",
    "address_review_diff",
    "address_review_diff_item",
    "address_review_item",
    "address_review_queue",
    "address_review_query",
    "build_review_diff",
    "build_review_queue",
    "build_review_queue_from_directory",
    "federation_review_diff_item_from_mapping",
    "federation_review_item_from_mapping",
    "load_review_queue",
    "query_review_diff",
    "query_review_queue",
    "render_review_diff_markdown",
    "render_review_queue_markdown",
    "render_review_query_markdown",
    "review_capabilities",
    "review_diff_csv",
    "review_diff_from_mapping",
    "review_diff_json",
    "review_diff_schema",
    "review_queue_csv",
    "review_queue_from_mapping",
    "review_queue_json",
    "review_queue_schema",
    "review_query_csv",
    "review_query_json",
    "review_query_schema",
    "verify_review_diff",
    "verify_review_queue",
    "write_review_queue",
]
