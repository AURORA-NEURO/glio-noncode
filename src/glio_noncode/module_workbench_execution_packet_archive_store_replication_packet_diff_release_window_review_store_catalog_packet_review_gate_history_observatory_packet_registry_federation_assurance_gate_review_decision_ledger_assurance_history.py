"""Maintain a deterministic longitudinal history of decision-assurance gates.

The decision-assurance gate describes one verified review-ledger snapshot.  This
module adds a narrow longitudinal projection over those snapshots: each
observation is addressed, ordered, linked to the previous observation, and
classified as initial, stable, improved, regressed, or changed.  The history
does not mutate or merge the source gates.  It retains only public summaries
and content addresses, which makes it suitable for repeatable real-data
handoffs without exposing paths, identities, timestamps, or runtime metadata.

The durable history package contains exactly ``manifest.json``,
``history.json``, and ``entries.json``.  Canonical bytes, per-file receipts,
entry ancestry, conserved counters, and terminal projections are verified on
reload.  A separate replay report independently checks the retained history
invariants and can be exported without changing the history.
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
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance as assurance_model,
)
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

DecisionAssuranceGate = assurance_model.DecisionAssuranceGate

VERSION = assurance_model.VERSION + "-history-v1"
BOUNDARY = "public_registry_federation_assurance_gate_review_decision_ledger_assurance_history"
ASSURANCE_PREFIX = assurance_model.ASSURANCE_PREFIX
HISTORY_PREFIX = assurance_model.ASSURANCE_PREFIX + "-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
REPLAY_PREFIX = HISTORY_PREFIX + "-replay"
REPLAY_CHECK_PREFIX = REPLAY_PREFIX + "-check"
QUERY_PREFIX = HISTORY_PREFIX + "-query"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
HISTORY_NAME = "history.json"
ENTRIES_NAME = "entries.json"
FILES = (MANIFEST_NAME, HISTORY_NAME, ENTRIES_NAME)
DEFAULT_HISTORY_ID = "glio-noncode-observatory-registry-federation-review-decision-assurance-history"
MAX_ENTRIES = 1024
MAX_QUERY_ITEMS = 4096
DEFAULT_LIMIT = 50

_FORBIDDEN_KEYS = frozenset({"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"})


class AssuranceHistoryState(StrEnum):
    """Current state derived from the terminal assurance gate."""

    EMPTY = "empty"
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"


class AssuranceHistoryTransition(StrEnum):
    """Semantic relationship between adjacent assurance observations."""

    INITIAL = "initial"
    STABLE = "stable"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    CHANGED = "changed"


class HistoryReplayState(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be an address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    return None if value is None else _address(value, field)


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _optional_bool(value: Any, field: str) -> bool | None:
    return None if value is None else _bool(value, field)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _mapping_sequence(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    return tuple(_mapping(item, field) for item in value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unknown fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in _FORBIDDEN_KEYS and _public(key) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _history_state(gate_state: str) -> str:
    mapping = {"promote": AssuranceHistoryState.READY.value, "hold": AssuranceHistoryState.HELD.value, "block": AssuranceHistoryState.BLOCKED.value}
    try:
        return mapping[gate_state]
    except KeyError as exc:
        raise ValidationError("gate state cannot become a history state") from exc


def _gate_state(value: Any, field: str = "gate state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in assurance_model.GateState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _assurance_state(value: Any, field: str = "assurance state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in assurance_model.AssuranceState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _history_state_value(value: Any, field: str = "history state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in AssuranceHistoryState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _transition(value: Any, field: str = "history transition") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in AssuranceHistoryTransition}:
        raise ValidationError(f"{field} is invalid")
    return value


def _replay_state(value: Any, field: str = "replay state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in HistoryReplayState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _score(gate_state: str) -> int:
    return {"block": 0, "hold": 1, "promote": 2}[gate_state]


class DecisionAssuranceHistoryEntry:
    """One addressed assurance-gate observation in a longitudinal chain."""

    def __init__(self, ordinal: int, entry_id: str, snapshot_id: str, assurance_id: str, ledger_id: str, assurance_address: str, gate_address: str, ledger_address: str, assurance_state: str, gate_state: str, snapshot_state: str, accepted: bool, release_ready: bool, source_queue_release_ready: bool, finding_count: int, warning_count: int, blocker_count: int, check_count: int, passed_count: int, previous_entry_address: str | None, previous_assurance_address: str | None, previous_gate_address: str | None, previous_snapshot_state: str | None, previous_gate_state: str | None, previous_release_ready: bool | None, transition: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.entry_id = entry_id
        self.snapshot_id = snapshot_id
        self.assurance_id = assurance_id
        self.ledger_id = ledger_id
        self.assurance_address = assurance_address
        self.gate_address = gate_address
        self.ledger_address = ledger_address
        self.assurance_state = assurance_state
        self.gate_state = gate_state
        self.snapshot_state = snapshot_state
        self.accepted = accepted
        self.release_ready = release_ready
        self.source_queue_release_ready = source_queue_release_ready
        self.finding_count = finding_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.check_count = check_count
        self.passed_count = passed_count
        self.previous_entry_address = previous_entry_address
        self.previous_assurance_address = previous_assurance_address
        self.previous_gate_address = previous_gate_address
        self.previous_snapshot_state = previous_snapshot_state
        self.previous_gate_state = previous_gate_state
        self.previous_release_ready = previous_release_ready
        self.transition = transition
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "history entry ordinal", MAX_ENTRIES)
        _text(self.entry_id, "history entry ID", 256)
        _text(self.snapshot_id, "history snapshot ID", 256)
        _text(self.assurance_id, "history assurance ID", 256)
        _text(self.ledger_id, "history ledger ID", 256)
        for value, field in ((self.assurance_address, "history assurance address"), (self.gate_address, "history gate address"), (self.ledger_address, "history ledger address")):
            _address(value, field)
        _assurance_state(self.assurance_state)
        _gate_state(self.gate_state)
        _history_state_value(self.snapshot_state)
        if self.snapshot_state != _history_state(self.gate_state):
            raise ValidationError("history snapshot state does not match gate state")
        for value, field in ((self.accepted, "history accepted"), (self.release_ready, "history release readiness"), (self.source_queue_release_ready, "history source queue readiness")):
            _bool(value, field)
        for value, field in ((self.finding_count, "finding count"), (self.warning_count, "warning count"), (self.blocker_count, "blocker count"), (self.check_count, "check count"), (self.passed_count, "passed count")):
            _count(value, f"history {field}", 4096)
        if self.passed_count + self.warning_count + self.blocker_count != self.finding_count + self.check_count:
            raise ValidationError("history observation quality counts are not conserved")
        _optional_address(self.previous_entry_address, "previous history entry address")
        _optional_address(self.previous_assurance_address, "previous assurance address")
        _optional_address(self.previous_gate_address, "previous gate address")
        if self.ordinal == 0:
            if any(value is not None for value in (self.previous_entry_address, self.previous_assurance_address, self.previous_gate_address, self.previous_snapshot_state, self.previous_gate_state, self.previous_release_ready)):
                raise ValidationError("initial history entry cannot have previous snapshot fields")
            if self.transition != AssuranceHistoryTransition.INITIAL.value:
                raise ValidationError("initial history entry must have initial transition")
        else:
            for value, field in ((self.previous_snapshot_state, "previous snapshot state"), (self.previous_gate_state, "previous gate state")):
                if value is None:
                    raise ValidationError(f"{field} is required after initial entry")
            _history_state_value(self.previous_snapshot_state, "previous snapshot state")
            _gate_state(self.previous_gate_state, "previous gate state")
            _optional_bool(self.previous_release_ready, "previous release readiness")
            for value, field in ((self.previous_entry_address, "previous entry address"), (self.previous_assurance_address, "previous assurance address"), (self.previous_gate_address, "previous gate address")):
                _address(value, field)
            if self.transition == AssuranceHistoryTransition.INITIAL.value:
                raise ValidationError("non-initial history entry cannot have initial transition")
        _transition(self.transition)
        _address(self.content_address, "history entry address")
        if not _public(self.to_dict()):
            raise ValidationError("history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "entry_id": self.entry_id, "snapshot_id": self.snapshot_id, "assurance_id": self.assurance_id, "ledger_id": self.ledger_id, "assurance_address": self.assurance_address, "gate_address": self.gate_address, "ledger_address": self.ledger_address, "assurance_state": self.assurance_state, "gate_state": self.gate_state, "snapshot_state": self.snapshot_state, "accepted": self.accepted, "release_ready": self.release_ready, "source_queue_release_ready": self.source_queue_release_ready, "finding_count": self.finding_count, "warning_count": self.warning_count, "blocker_count": self.blocker_count, "check_count": self.check_count, "passed_count": self.passed_count, "previous_entry_address": self.previous_entry_address, "previous_assurance_address": self.previous_assurance_address, "previous_gate_address": self.previous_gate_address, "previous_snapshot_state": self.previous_snapshot_state, "previous_gate_state": self.previous_gate_state, "previous_release_ready": self.previous_release_ready, "transition": self.transition, "content_address": self.content_address}


def address_decision_assurance_history_entry(value: DecisionAssuranceHistoryEntry) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class DecisionAssuranceHistory:
    """Ordered, append-only assurance snapshot history."""

    def __init__(self, history_id: str, version: str, boundary: str, entry_count: int, initial_snapshot_id: str | None, current_snapshot_id: str | None, current_assurance_address: str | None, current_gate_address: str | None, current_ledger_address: str | None, current_assurance_state: str | None, current_gate_state: str | None, current_state: str, current_accepted: bool, current_release_ready: bool, initial_count: int, stable_count: int, improved_count: int, regressed_count: int, changed_count: int, accepted_count: int, release_ready_count: int, head_address: str | None, entries: Sequence[DecisionAssuranceHistoryEntry], content_address: str) -> None:
        self.history_id = history_id
        self.version = version
        self.boundary = boundary
        self.entry_count = entry_count
        self.initial_snapshot_id = initial_snapshot_id
        self.current_snapshot_id = current_snapshot_id
        self.current_assurance_address = current_assurance_address
        self.current_gate_address = current_gate_address
        self.current_ledger_address = current_ledger_address
        self.current_assurance_state = current_assurance_state
        self.current_gate_state = current_gate_state
        self.current_state = current_state
        self.current_accepted = current_accepted
        self.current_release_ready = current_release_ready
        self.initial_count = initial_count
        self.stable_count = stable_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.changed_count = changed_count
        self.accepted_count = accepted_count
        self.release_ready_count = release_ready_count
        self.head_address = head_address
        self.entries = tuple(entries)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.history_id, "assurance history ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("assurance history contract is invalid")
        _count(self.entry_count, "assurance history entry count", MAX_ENTRIES)
        if self.entry_count != len(self.entries):
            raise ValidationError("assurance history entry count is not conserved")
        transition_counts = {item.value: 0 for item in AssuranceHistoryTransition}
        snapshot_ids: set[str] = set()
        for ordinal, entry in enumerate(self.entries):
            if not isinstance(entry, DecisionAssuranceHistoryEntry) or entry.ordinal != ordinal:
                raise ValidationError("assurance history entry ordinals are not contiguous")
            if address_decision_assurance_history_entry(entry) != entry.content_address:
                raise ValidationError("assurance history entry address mismatch")
            if entry.snapshot_id in snapshot_ids:
                raise ValidationError("assurance history snapshot IDs are not unique")
            if ordinal == 0:
                if entry.previous_entry_address is not None:
                    raise ValidationError("initial history entry has a previous link")
            elif entry.previous_entry_address != self.entries[ordinal - 1].content_address or entry.previous_assurance_address != self.entries[ordinal - 1].assurance_address or entry.previous_gate_address != self.entries[ordinal - 1].gate_address:
                raise ValidationError("assurance history ancestry is not contiguous")
            transition_counts[entry.transition] += 1
            snapshot_ids.add(entry.snapshot_id)
        if (self.initial_count, self.stable_count, self.improved_count, self.regressed_count, self.changed_count) != tuple(transition_counts[item.value] for item in AssuranceHistoryTransition):
            raise ValidationError("assurance history transition counts are not conserved")
        for count, field in ((self.initial_count, "initial count"), (self.stable_count, "stable count"), (self.improved_count, "improved count"), (self.regressed_count, "regressed count"), (self.changed_count, "changed count"), (self.accepted_count, "accepted count"), (self.release_ready_count, "release-ready count")):
            _count(count, f"assurance history {field}", MAX_ENTRIES)
        if self.accepted_count > self.entry_count or self.release_ready_count > self.entry_count:
            raise ValidationError("assurance history projection counts exceed entries")
        if not self.entries:
            if self.initial_snapshot_id is not None or self.current_snapshot_id is not None or any(value is not None for value in (self.current_assurance_address, self.current_gate_address, self.current_ledger_address, self.current_assurance_state, self.current_gate_state)):
                raise ValidationError("empty assurance history has current projection fields")
            if self.current_state != AssuranceHistoryState.EMPTY.value or self.current_accepted or self.current_release_ready or self.head_address is not None:
                raise ValidationError("empty assurance history projection is invalid")
        else:
            terminal = self.entries[-1]
            if self.initial_snapshot_id != self.entries[0].snapshot_id or self.current_snapshot_id != terminal.snapshot_id or self.current_assurance_address != terminal.assurance_address or self.current_gate_address != terminal.gate_address or self.current_ledger_address != terminal.ledger_address or self.current_assurance_state != terminal.assurance_state or self.current_gate_state != terminal.gate_state or self.current_state != terminal.snapshot_state or self.current_accepted != terminal.accepted or self.current_release_ready != terminal.release_ready or self.head_address != terminal.content_address:
                raise ValidationError("assurance history terminal projection is invalid")
        _history_state_value(self.current_state)
        _optional_address(self.current_assurance_address, "current assurance address")
        _optional_address(self.current_gate_address, "current gate address")
        _optional_address(self.current_ledger_address, "current ledger address")
        if self.current_assurance_state is not None:
            _assurance_state(self.current_assurance_state, "current assurance state")
        if self.current_gate_state is not None:
            _gate_state(self.current_gate_state, "current gate state")
        _bool(self.current_accepted, "current accepted")
        _bool(self.current_release_ready, "current release readiness")
        _optional_address(self.head_address, "assurance history head address")
        _address(self.content_address, "assurance history address")
        if not _public(self.to_dict()):
            raise ValidationError("assurance history crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "initial_snapshot_id": self.initial_snapshot_id, "current_snapshot_id": self.current_snapshot_id, "current_assurance_address": self.current_assurance_address, "current_gate_address": self.current_gate_address, "current_ledger_address": self.current_ledger_address, "current_assurance_state": self.current_assurance_state, "current_gate_state": self.current_gate_state, "current_state": self.current_state, "current_accepted": self.current_accepted, "current_release_ready": self.current_release_ready, "initial_count": self.initial_count, "stable_count": self.stable_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "changed_count": self.changed_count, "accepted_count": self.accepted_count, "release_ready_count": self.release_ready_count, "head_address": self.head_address, "content_address": self.content_address}

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_entries:
            body["entries"] = [entry.to_dict() for entry in self.entries]
        return body


def address_decision_assurance_history(value: DecisionAssuranceHistory) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def _history_transition(previous: DecisionAssuranceHistoryEntry | None, gate: DecisionAssuranceGate) -> str:
    if previous is None:
        return AssuranceHistoryTransition.INITIAL.value
    current_gate_state = gate.gate.state
    if _score(current_gate_state) > _score(previous.gate_state):
        return AssuranceHistoryTransition.IMPROVED.value
    if _score(current_gate_state) < _score(previous.gate_state):
        return AssuranceHistoryTransition.REGRESSED.value
    semantic = (gate.assurance.state, current_gate_state, gate.gate.accepted, gate.gate.release_ready, gate.gate.source_queue_release_ready, gate.assurance.finding_count, gate.assurance.warning_count + gate.gate.warning_count, gate.assurance.blocker_count + gate.gate.blocker_count, gate.gate.check_count, gate.assurance.passed_count + gate.gate.passed_count)
    previous_semantic = (previous.assurance_state, previous.gate_state, previous.accepted, previous.release_ready, previous.source_queue_release_ready, previous.finding_count, previous.warning_count, previous.blocker_count, previous.check_count, previous.passed_count)
    return AssuranceHistoryTransition.STABLE.value if semantic == previous_semantic else AssuranceHistoryTransition.CHANGED.value


def _empty_history(history_id: str) -> DecisionAssuranceHistory:
    body = {"history_id": _text(history_id, "assurance history ID", 256), "version": VERSION, "boundary": BOUNDARY, "entry_count": 0, "initial_snapshot_id": None, "current_snapshot_id": None, "current_assurance_address": None, "current_gate_address": None, "current_ledger_address": None, "current_assurance_state": None, "current_gate_state": None, "current_state": AssuranceHistoryState.EMPTY.value, "current_accepted": False, "current_release_ready": False, "initial_count": 0, "stable_count": 0, "improved_count": 0, "regressed_count": 0, "changed_count": 0, "accepted_count": 0, "release_ready_count": 0, "head_address": None, "entries": ()}
    return DecisionAssuranceHistory(**body, content_address=address_decision_assurance_history(DecisionAssuranceHistory(**body, content_address="pending:history")))


def _history_body(history: DecisionAssuranceHistory, entries: Sequence[DecisionAssuranceHistoryEntry]) -> dict[str, Any]:
    transitions = {item.value: sum(entry.transition == item.value for entry in entries) for item in AssuranceHistoryTransition}
    terminal = entries[-1] if entries else None
    return {"history_id": history.history_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": len(entries), "initial_snapshot_id": entries[0].snapshot_id if entries else None, "current_snapshot_id": terminal.snapshot_id if terminal else None, "current_assurance_address": terminal.assurance_address if terminal else None, "current_gate_address": terminal.gate_address if terminal else None, "current_ledger_address": terminal.ledger_address if terminal else None, "current_assurance_state": terminal.assurance_state if terminal else None, "current_gate_state": terminal.gate_state if terminal else None, "current_state": terminal.snapshot_state if terminal else AssuranceHistoryState.EMPTY.value, "current_accepted": terminal.accepted if terminal else False, "current_release_ready": terminal.release_ready if terminal else False, "initial_count": transitions[AssuranceHistoryTransition.INITIAL.value], "stable_count": transitions[AssuranceHistoryTransition.STABLE.value], "improved_count": transitions[AssuranceHistoryTransition.IMPROVED.value], "regressed_count": transitions[AssuranceHistoryTransition.REGRESSED.value], "changed_count": transitions[AssuranceHistoryTransition.CHANGED.value], "accepted_count": sum(entry.accepted for entry in entries), "release_ready_count": sum(entry.release_ready for entry in entries), "head_address": terminal.content_address if terminal else None, "entries": tuple(entries)}


def append_decision_assurance_history(history: DecisionAssuranceHistory, gate: DecisionAssuranceGate, *, snapshot_id: str | None = None, entry_id: str | None = None, expected_head_address: str | None = None) -> DecisionAssuranceHistory:
    if not isinstance(history, DecisionAssuranceHistory) or not isinstance(gate, DecisionAssuranceGate):
        raise ValidationError("assurance history append requires typed history and gate")
    verify_decision_assurance_history(history)
    assurance_model.verify_decision_assurance_gate(gate)
    if expected_head_address is not None and expected_head_address != history.head_address:
        raise ValidationError("assurance history expected head does not match")
    if history.entry_count >= MAX_ENTRIES:
        raise ValidationError("assurance history entry limit exceeded")
    next_snapshot_id = _text(snapshot_id or f"{history.history_id}:snapshot:{history.entry_count}", "assurance snapshot ID", 256)
    if any(entry.snapshot_id == next_snapshot_id for entry in history.entries):
        raise ValidationError("assurance snapshot ID already exists")
    next_entry_id = _text(entry_id or f"{history.history_id}:entry:{history.entry_count}", "assurance history entry ID", 256)
    if any(entry.entry_id == next_entry_id for entry in history.entries):
        raise ValidationError("assurance history entry ID already exists")
    previous = history.entries[-1] if history.entries else None
    body = {"ordinal": history.entry_count, "entry_id": next_entry_id, "snapshot_id": next_snapshot_id, "assurance_id": gate.assurance.assurance_id, "ledger_id": gate.gate.ledger_id, "assurance_address": gate.assurance.content_address, "gate_address": gate.gate.content_address, "ledger_address": gate.gate.ledger_address, "assurance_state": gate.assurance.state, "gate_state": gate.gate.state, "snapshot_state": _history_state(gate.gate.state), "accepted": gate.gate.accepted, "release_ready": gate.gate.release_ready, "source_queue_release_ready": gate.gate.source_queue_release_ready, "finding_count": gate.assurance.finding_count, "warning_count": gate.assurance.warning_count + gate.gate.warning_count, "blocker_count": gate.assurance.blocker_count + gate.gate.blocker_count, "check_count": gate.gate.check_count, "passed_count": gate.assurance.passed_count + gate.gate.passed_count, "previous_entry_address": previous.content_address if previous else None, "previous_assurance_address": previous.assurance_address if previous else None, "previous_gate_address": previous.gate_address if previous else None, "previous_snapshot_state": previous.snapshot_state if previous else None, "previous_gate_state": previous.gate_state if previous else None, "previous_release_ready": previous.release_ready if previous else None, "transition": _history_transition(previous, gate)}
    provisional_entry = DecisionAssuranceHistoryEntry(**body, content_address="pending:entry")
    entry = DecisionAssuranceHistoryEntry(**body, content_address=address_decision_assurance_history_entry(provisional_entry))
    entries = history.entries + (entry,)
    next_body = _history_body(history, entries)
    provisional_history = DecisionAssuranceHistory(**next_body, content_address="pending:history")
    return DecisionAssuranceHistory(**next_body, content_address=address_decision_assurance_history(provisional_history))


def build_decision_assurance_history(gate: DecisionAssuranceGate, *, history_id: str = DEFAULT_HISTORY_ID, snapshot_id: str | None = None, entry_id: str | None = None) -> DecisionAssuranceHistory:
    return append_decision_assurance_history(_empty_history(history_id), gate, snapshot_id=snapshot_id, entry_id=entry_id)


def verify_decision_assurance_history(value: DecisionAssuranceHistory) -> DecisionAssuranceHistory:
    if not isinstance(value, DecisionAssuranceHistory):
        raise ValidationError("assurance history verification requires a typed history")
    for entry in value.entries:
        if address_decision_assurance_history_entry(entry) != entry.content_address:
            raise ValidationError("assurance history entry address mismatch")
    if address_decision_assurance_history(value) != value.content_address:
        raise ValidationError("assurance history address mismatch")
    return value


def decision_assurance_history_entry_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistoryEntry:
    body = dict(_mapping(value, "assurance history entry"))
    _strict(body, {"ordinal", "entry_id", "snapshot_id", "assurance_id", "ledger_id", "assurance_address", "gate_address", "ledger_address", "assurance_state", "gate_state", "snapshot_state", "accepted", "release_ready", "source_queue_release_ready", "finding_count", "warning_count", "blocker_count", "check_count", "passed_count", "previous_entry_address", "previous_assurance_address", "previous_gate_address", "previous_snapshot_state", "previous_gate_state", "previous_release_ready", "transition", "content_address"}, "assurance history entry")
    entry = DecisionAssuranceHistoryEntry(**body)
    if address_decision_assurance_history_entry(entry) != entry.content_address:
        raise ValidationError("assurance history entry address mismatch")
    return entry


def decision_assurance_history_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistory:
    body = dict(_mapping(value, "assurance history"))
    _strict(body, {"history_id", "version", "boundary", "entry_count", "initial_snapshot_id", "current_snapshot_id", "current_assurance_address", "current_gate_address", "current_ledger_address", "current_assurance_state", "current_gate_state", "current_state", "current_accepted", "current_release_ready", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "accepted_count", "release_ready_count", "head_address", "entries", "content_address"}, "assurance history")
    body["entries"] = tuple(decision_assurance_history_entry_from_mapping(item) for item in _mapping_sequence(body["entries"], "assurance history entries"))
    return verify_decision_assurance_history(DecisionAssuranceHistory(**body))


class DecisionAssuranceHistoryReplayCheck:
    """One independent replay invariant."""

    def __init__(self, ordinal: int, check_id: str, kind: str, passed: bool, required: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.check_id = check_id
        self.kind = kind
        self.passed = passed
        self.required = required
        self.detail = detail
        self.evidence_address = evidence_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "history replay check ordinal", 32)
        _text(self.check_id, "history replay check ID", 256)
        _text(self.kind, "history replay check kind", 128)
        _bool(self.passed, "history replay check passed")
        _bool(self.required, "history replay check required")
        _text(self.detail, "history replay check detail", 2048)
        _address(self.evidence_address, "history replay evidence address")
        _address(self.content_address, "history replay check address")
        if not _public(self.to_dict()):
            raise ValidationError("history replay check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "kind": self.kind, "passed": self.passed, "required": self.required, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}


def address_decision_assurance_history_replay_check(value: DecisionAssuranceHistoryReplayCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REPLAY_CHECK_PREFIX)


class DecisionAssuranceHistoryReplay:
    """Independent replay receipt for a retained assurance history."""

    def __init__(self, history_address: str, history_id: str, entry_count: int, head_address: str | None, current_state: str, current_gate_state: str | None, check_count: int, passed_count: int, failure_count: int, state: str, accepted: bool, release_ready: bool, checks: Sequence[DecisionAssuranceHistoryReplayCheck], content_address: str) -> None:
        self.history_address = history_address
        self.history_id = history_id
        self.entry_count = entry_count
        self.head_address = head_address
        self.current_state = current_state
        self.current_gate_state = current_gate_state
        self.check_count = check_count
        self.passed_count = passed_count
        self.failure_count = failure_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.history_address, "replay history address")
        _text(self.history_id, "replay history ID", 256)
        _count(self.entry_count, "replay entry count", MAX_ENTRIES)
        _optional_address(self.head_address, "replay head address")
        _history_state_value(self.current_state, "replay current state")
        if self.current_gate_state is not None:
            _gate_state(self.current_gate_state, "replay current gate state")
        _count(self.check_count, "replay check count", 32)
        if self.check_count != len(self.checks):
            raise ValidationError("replay check count is not conserved")
        _count(self.passed_count, "replay passed count", 32)
        _count(self.failure_count, "replay failure count", 32)
        if self.passed_count + self.failure_count != self.check_count:
            raise ValidationError("replay result counts are not conserved")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, DecisionAssuranceHistoryReplayCheck) or check.ordinal != ordinal:
                raise ValidationError("replay check ordinals are not contiguous")
            if address_decision_assurance_history_replay_check(check) != check.content_address:
                raise ValidationError("replay check address mismatch")
        _replay_state(self.state)
        _bool(self.accepted, "replay accepted")
        _bool(self.release_ready, "replay release readiness")
        if self.accepted != (self.failure_count == 0) or self.state != (HistoryReplayState.PASSED.value if self.accepted else HistoryReplayState.BLOCKED.value):
            raise ValidationError("replay state is not conserved")
        _address(self.content_address, "replay address")
        if not _public(self.to_dict()):
            raise ValidationError("history replay crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "history_id": self.history_id, "entry_count": self.entry_count, "head_address": self.head_address, "current_state": self.current_state, "current_gate_state": self.current_gate_state, "check_count": self.check_count, "passed_count": self.passed_count, "failure_count": self.failure_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        body = self.summary()
        body["checks"] = [check.to_dict() for check in self.checks]
        return body


def address_decision_assurance_history_replay(value: DecisionAssuranceHistoryReplay) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REPLAY_PREFIX)


def _replay_check(ordinal: int, history: DecisionAssuranceHistory, kind: str, passed: bool, detail: str) -> DecisionAssuranceHistoryReplayCheck:
    body = {"ordinal": ordinal, "check_id": f"{history.history_id}:replay:{ordinal}", "kind": kind, "passed": bool(passed), "required": True, "detail": detail, "evidence_address": history.content_address}
    provisional = DecisionAssuranceHistoryReplayCheck(**body, content_address="pending:replay-check")
    return DecisionAssuranceHistoryReplayCheck(**body, content_address=address_decision_assurance_history_replay_check(provisional))


def replay_decision_assurance_history(history: DecisionAssuranceHistory) -> DecisionAssuranceHistoryReplay:
    verify_decision_assurance_history(history)
    entries = history.entries
    checks = (
        _replay_check(0, history, "entry-addresses", all(address_decision_assurance_history_entry(entry) == entry.content_address for entry in entries), "every retained entry address recomputes"),
        _replay_check(1, history, "ordinal-continuity", all(entry.ordinal == ordinal for ordinal, entry in enumerate(entries)), "entry ordinals are contiguous from zero"),
        _replay_check(2, history, "ancestry-continuity", all(ordinal == 0 or entry.previous_entry_address == entries[ordinal - 1].content_address and entry.previous_assurance_address == entries[ordinal - 1].assurance_address and entry.previous_gate_address == entries[ordinal - 1].gate_address for ordinal, entry in enumerate(entries)), "previous entry and snapshot links form one chain"),
        _replay_check(3, history, "transition-counters", history.initial_count + history.stable_count + history.improved_count + history.regressed_count + history.changed_count == history.entry_count, "transition counters equal retained observations"),
        _replay_check(4, history, "terminal-projection", not entries or history.head_address == entries[-1].content_address and history.current_snapshot_id == entries[-1].snapshot_id and history.current_state == entries[-1].snapshot_state, "terminal state and head reproduce the final observation"),
        _replay_check(5, history, "unique-snapshots", len({entry.snapshot_id for entry in entries}) == history.entry_count, "snapshot identifiers are unique"),
        _replay_check(6, history, "public-boundary", _public(history.to_dict()), "history projection contains only public fields"),
    )
    passed = sum(check.passed for check in checks)
    failures = len(checks) - passed
    body = {"history_address": history.content_address, "history_id": history.history_id, "entry_count": history.entry_count, "head_address": history.head_address, "current_state": history.current_state, "current_gate_state": history.current_gate_state, "check_count": len(checks), "passed_count": passed, "failure_count": failures, "state": HistoryReplayState.PASSED.value if failures == 0 else HistoryReplayState.BLOCKED.value, "accepted": failures == 0, "release_ready": failures == 0 and history.current_release_ready, "checks": checks}
    provisional = DecisionAssuranceHistoryReplay(**body, content_address="pending:replay")
    return DecisionAssuranceHistoryReplay(**body, content_address=address_decision_assurance_history_replay(provisional))


def verify_decision_assurance_history_replay(value: DecisionAssuranceHistoryReplay) -> DecisionAssuranceHistoryReplay:
    if not isinstance(value, DecisionAssuranceHistoryReplay):
        raise ValidationError("history replay verification requires a typed replay")
    for check in value.checks:
        if address_decision_assurance_history_replay_check(check) != check.content_address:
            raise ValidationError("history replay check address mismatch")
    if address_decision_assurance_history_replay(value) != value.content_address:
        raise ValidationError("history replay address mismatch")
    return value


def decision_assurance_history_replay_check_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistoryReplayCheck:
    body = dict(_mapping(value, "history replay check"))
    _strict(body, {"ordinal", "check_id", "kind", "passed", "required", "detail", "evidence_address", "content_address"}, "history replay check")
    check = DecisionAssuranceHistoryReplayCheck(**body)
    if address_decision_assurance_history_replay_check(check) != check.content_address:
        raise ValidationError("history replay check address mismatch")
    return check


def decision_assurance_history_replay_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistoryReplay:
    body = dict(_mapping(value, "history replay"))
    _strict(body, {"history_address", "history_id", "entry_count", "head_address", "current_state", "current_gate_state", "check_count", "passed_count", "failure_count", "state", "accepted", "release_ready", "checks", "content_address"}, "history replay")
    body["checks"] = tuple(decision_assurance_history_replay_check_from_mapping(item) for item in _mapping_sequence(body["checks"], "history replay checks"))
    return verify_decision_assurance_history_replay(DecisionAssuranceHistoryReplay(**body))


class AssuranceHistoryQuery:
    """Bounded query over history summaries or ordered observations."""

    def __init__(self, resource: str = "summary", *, transition: str | None = None, snapshot_state: str | None = None, gate_state: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "assurance history query resource", 64)
        allowed = {"summary", "entries", "transitions", "ready", "held", "blocked", "initial", "stable", "improved", "regressed", "changed", "accepted", "release-ready"}
        if self.resource not in allowed:
            raise ValidationError("assurance history query resource is invalid")
        if transition is not None:
            _transition(transition, "assurance history query transition")
        if snapshot_state is not None:
            _history_state_value(snapshot_state, "assurance history query snapshot state")
        if gate_state is not None:
            _gate_state(gate_state, "assurance history query gate state")
        self.transition = transition
        self.snapshot_state = snapshot_state
        self.gate_state = gate_state
        self.text = _text(text, "assurance history query text", 256).casefold() if text is not None else None
        self.offset = _count(offset, "assurance history query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "assurance history query limit", MAX_QUERY_ITEMS, positive=True)
        if self.offset + self.limit > MAX_QUERY_ITEMS:
            raise ValidationError("assurance history query window is too large")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "transition": self.transition, "snapshot_state": self.snapshot_state, "gate_state": self.gate_state, "text": self.text, "offset": self.offset, "limit": self.limit}


class AssuranceHistoryQueryResult:
    def __init__(self, query: AssuranceHistoryQuery, total_count: int, items: Sequence[Mapping[str, Any]], source_address: str) -> None:
        self.query = query
        self.total_count = _count(total_count, "assurance history query total count", MAX_QUERY_ITEMS)
        self.items = tuple(dict(item) for item in items)
        self.returned_count = _count(len(self.items), "assurance history query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count:
            raise ValidationError("assurance history query returned count exceeds total")
        self.source_address = _address(source_address, "assurance history query source address")
        self.content_address = "pending:history-query"
        self.content_address = content_hash(self.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-result")
        if not _public(self.to_dict()):
            raise ValidationError("assurance history query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "source_address": self.source_address, "content_address": self.content_address}


def query_decision_assurance_history(history: DecisionAssuranceHistory, query: AssuranceHistoryQuery | None = None, **kwargs: Any) -> AssuranceHistoryQueryResult:
    verify_decision_assurance_history(history)
    selected = query if query is not None else AssuranceHistoryQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    if selected.resource == "summary":
        records: tuple[Mapping[str, Any], ...] = (history.summary(),)
    else:
        records = tuple(entry.to_dict() for entry in history.entries)
        if selected.resource in {item.value for item in AssuranceHistoryTransition}:
            records = tuple(item for item in records if item["transition"] == selected.resource)
        elif selected.resource in {item.value for item in AssuranceHistoryState if item != AssuranceHistoryState.EMPTY}:
            records = tuple(item for item in records if item["snapshot_state"] == selected.resource)
        elif selected.resource == "accepted":
            records = tuple(item for item in records if item["accepted"])
        elif selected.resource == "release-ready":
            records = tuple(item for item in records if item["release_ready"])
    matched = tuple(item for item in records if (selected.transition is None or item.get("transition") == selected.transition) and (selected.snapshot_state is None or item.get("snapshot_state") == selected.snapshot_state) and (selected.gate_state is None or item.get("gate_state") == selected.gate_state) and (selected.text is None or selected.text in canonical_json(item).casefold()))
    return AssuranceHistoryQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], history.content_address)


def decision_assurance_history_json(value: DecisionAssuranceHistory) -> str:
    verify_decision_assurance_history(value)
    return canonical_json(value.to_dict())


def decision_assurance_history_csv(value: DecisionAssuranceHistory) -> str:
    verify_decision_assurance_history(value)
    rows = [entry.to_dict() for entry in value.entries]
    fields = ("ordinal", "entry_id", "snapshot_id", "assurance_id", "ledger_id", "assurance_address", "gate_address", "ledger_address", "assurance_state", "gate_state", "snapshot_state", "accepted", "release_ready", "source_queue_release_ready", "finding_count", "warning_count", "blocker_count", "check_count", "passed_count", "previous_entry_address", "previous_assurance_address", "previous_gate_address", "previous_snapshot_state", "previous_gate_state", "previous_release_ready", "transition", "content_address")
    return _csv_text(rows, fields)


def decision_assurance_history_replay_json(value: DecisionAssuranceHistoryReplay) -> str:
    verify_decision_assurance_history_replay(value)
    return canonical_json(value.to_dict())


def decision_assurance_history_replay_csv(value: DecisionAssuranceHistoryReplay) -> str:
    verify_decision_assurance_history_replay(value)
    return _csv_text([check.to_dict() for check in value.checks], ("ordinal", "check_id", "kind", "passed", "required", "detail", "evidence_address", "content_address"))


def decision_assurance_history_query_json(value: AssuranceHistoryQueryResult) -> str:
    return canonical_json(value.to_dict())


def decision_assurance_history_query_csv(value: AssuranceHistoryQueryResult) -> str:
    if not value.items:
        return ""
    return _csv_text(value.items, tuple(sorted({key for item in value.items for key in item})))


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", ""]
    for key, value in summary.items():
        lines.append(f"- **{key}**: `{canonical_json(value)}`")
    if rows:
        lines.extend(("", "## Records", ""))
        fields = tuple(rows[0])
        lines.append("| " + " | ".join(fields) + " |")
        lines.append("| " + " | ".join("---" for _ in fields) + " |")
        for row in rows:
            lines.append("| " + " | ".join(canonical_json(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    else:
        lines.extend(("", "No records."))
    return "\n".join(lines) + "\n"


def render_decision_assurance_history_markdown(value: DecisionAssuranceHistory) -> str:
    verify_decision_assurance_history(value)
    return _markdown("Federation Review Decision Assurance History", value.summary(), [entry.to_dict() for entry in value.entries])


def render_decision_assurance_history_replay_markdown(value: DecisionAssuranceHistoryReplay) -> str:
    verify_decision_assurance_history_replay(value)
    return _markdown("Federation Review Decision Assurance History Replay", value.summary(), [check.to_dict() for check in value.checks])


def render_decision_assurance_history_query_markdown(value: AssuranceHistoryQueryResult) -> str:
    return _markdown("Federation Review Decision Assurance History Query", {"resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def decision_assurance_history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History", "type": "object", "additionalProperties": False, "properties": {"history_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "entry_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "current_state": {"enum": [item.value for item in AssuranceHistoryState]}, "entries": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["history_id", "version", "boundary", "entry_count", "current_state", "content_address"]}


def decision_assurance_history_entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Entry", "type": "object", "additionalProperties": False, "properties": {"ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "snapshot_id": {"type": "string"}, "transition": {"enum": [item.value for item in AssuranceHistoryTransition]}, "snapshot_state": {"enum": [item.value for item in AssuranceHistoryState]}, "content_address": {"type": "string"}}, "required": ["ordinal", "snapshot_id", "transition", "snapshot_state", "content_address"]}


def decision_assurance_history_replay_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Replay", "type": "object", "additionalProperties": False, "properties": {"history_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "entry_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "check_count": {"type": "integer", "minimum": 0, "maximum": 32}, "state": {"enum": [item.value for item in HistoryReplayState]}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}, "required": ["history_address", "entry_count", "check_count", "state", "accepted", "content_address"]}


def decision_assurance_history_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": ["summary", "entries", "transitions", "ready", "held", "blocked", "initial", "stable", "improved", "regressed", "changed", "accepted", "release-ready"]}, "transition": {"type": ["string", "null"]}, "snapshot_state": {"type": ["string", "null"]}, "gate_state": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}, "required": ["resource", "offset", "limit"]}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "history": {"maximum_entries": MAX_ENTRIES, "states": [item.value for item in AssuranceHistoryState], "transitions": [item.value for item in AssuranceHistoryTransition]}, "replay": {"checks": 7, "states": [item.value for item in HistoryReplayState]}, "persistence": {"files": list(FILES), "atomic_write": True, "canonical_json": True, "exact_file_set": True}, "queries": {"resources": ["summary", "entries", "transitions", "ready", "held", "blocked", "initial", "stable", "improved", "regressed", "changed", "accepted", "release-ready"], "pagination": True, "filters": ["transition", "snapshot_state", "gate_state", "text"]}}


def _manifest_body(value: DecisionAssuranceHistory, history_raw: bytes, entries_raw: bytes) -> dict[str, Any]:
    artifacts = [{"name": HISTORY_NAME, "bytes": len(history_raw), "byte_address": hash_bytes(history_raw), "file_address": content_hash({"name": HISTORY_NAME, "byte_address": hash_bytes(history_raw)}, prefix=HISTORY_PREFIX + "-file")}, {"name": ENTRIES_NAME, "bytes": len(entries_raw), "byte_address": hash_bytes(entries_raw), "file_address": content_hash({"name": ENTRIES_NAME, "byte_address": hash_bytes(entries_raw)}, prefix=HISTORY_PREFIX + "-file")}]
    return {"version": VERSION, "boundary": BOUNDARY, "history_id": value.history_id, "history_address": value.content_address, "head_address": value.head_address, "entry_count": value.entry_count, "artifact_count": 2, "files": list(FILES), "artifacts": artifacts, "manifest_address": None}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=MANIFEST_PREFIX)


def write_decision_assurance_history(value: DecisionAssuranceHistory, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_assurance_history(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("decision assurance history destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    history_raw = canonical_bytes(value.to_dict(include_entries=False))
    entries_raw = canonical_bytes({"history_id": value.history_id, "history_address": value.content_address, "entry_count": value.entry_count, "entries": [entry.to_dict() for entry in value.entries]})
    manifest = _manifest_body(value, history_raw, entries_raw)
    manifest["manifest_address"] = _manifest_address(manifest)
    manifest_raw = canonical_bytes(manifest)
    temporary = Path(tempfile.mkdtemp(prefix=f".{HISTORY_PREFIX}-", dir=str(destination.parent)))
    try:
        (temporary / HISTORY_NAME).write_bytes(history_raw)
        (temporary / ENTRIES_NAME).write_bytes(entries_raw)
        (temporary / MANIFEST_NAME).write_bytes(manifest_raw)
        if destination.exists():
            if not destination.is_dir():
                raise ValidationError("decision assurance history destination is not a directory")
            if any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("decision assurance history destination already exists")
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
    artifact = next((item for item in _mapping_sequence(manifest.get("artifacts"), "history manifest artifacts") if item.get("name") == name), None)
    if artifact is None:
        raise ValidationError(f"history manifest is missing {name}")
    raw = path.read_bytes()
    byte_address = hash_bytes(raw)
    if artifact.get("bytes") != len(raw) or artifact.get("byte_address") != byte_address:
        raise ValidationError(f"history {name} bytes are not addressed")
    if artifact.get("file_address") != content_hash({"name": name, "byte_address": byte_address}, prefix=HISTORY_PREFIX + "-file"):
        raise ValidationError(f"history {name} file address is invalid")


def load_decision_assurance_history(directory: str | Path) -> DecisionAssuranceHistory:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("decision assurance history input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(FILES):
        raise ValidationError("decision assurance history file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "assurance history manifest")
    _strict(manifest, {"version", "boundary", "history_id", "history_address", "head_address", "entry_count", "artifact_count", "files", "artifacts", "manifest_address"}, "assurance history manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 2 or tuple(manifest["files"]) != FILES:
        raise ValidationError("assurance history manifest contract is invalid")
    if manifest["manifest_address"] != _manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("assurance history manifest address mismatch")
    _check_artifact(manifest, source / HISTORY_NAME, HISTORY_NAME)
    _check_artifact(manifest, source / ENTRIES_NAME, ENTRIES_NAME)
    summary = _read_json(source / HISTORY_NAME, "assurance history summary")
    entries_body = _read_json(source / ENTRIES_NAME, "assurance history entries")
    _strict(entries_body, {"history_id", "history_address", "entry_count", "entries"}, "assurance history entries")
    if entries_body["history_id"] != manifest["history_id"] or entries_body["history_address"] != manifest["history_address"] or entries_body["entry_count"] != manifest["entry_count"]:
        raise ValidationError("assurance history entries linkage is invalid")
    summary["entries"] = entries_body["entries"]
    value = decision_assurance_history_from_mapping(summary)
    if value.history_id != manifest["history_id"] or value.content_address != manifest["history_address"] or value.head_address != manifest["head_address"]:
        raise ValidationError("assurance history manifest linkage is invalid")
    return verify_decision_assurance_history(value)


__all__ = ["ASSURANCE_PREFIX", "BOUNDARY", "DEFAULT_HISTORY_ID", "DEFAULT_LIMIT", "ENTRIES_NAME", "FILES", "HISTORY_NAME", "HISTORY_PREFIX", "MANIFEST_NAME", "MAX_ENTRIES", "MAX_QUERY_ITEMS", "AssuranceHistoryQuery", "AssuranceHistoryQueryResult", "AssuranceHistoryState", "AssuranceHistoryTransition", "DecisionAssuranceGate", "DecisionAssuranceHistory", "DecisionAssuranceHistoryEntry", "DecisionAssuranceHistoryReplay", "DecisionAssuranceHistoryReplayCheck", "HistoryReplayState", "address_decision_assurance_history", "address_decision_assurance_history_entry", "address_decision_assurance_history_replay", "address_decision_assurance_history_replay_check", "append_decision_assurance_history", "build_decision_assurance_history", "capabilities", "decision_assurance_history_csv", "decision_assurance_history_entry_from_mapping", "decision_assurance_history_entry_schema", "decision_assurance_history_from_mapping", "decision_assurance_history_json", "decision_assurance_history_query_csv", "decision_assurance_history_query_json", "decision_assurance_history_query_schema", "decision_assurance_history_replay_csv", "decision_assurance_history_replay_from_mapping", "decision_assurance_history_replay_json", "decision_assurance_history_replay_schema", "decision_assurance_history_schema", "decision_assurance_history_replay_check_from_mapping", "load_decision_assurance_history", "query_decision_assurance_history", "replay_decision_assurance_history", "render_decision_assurance_history_markdown", "render_decision_assurance_history_query_markdown", "render_decision_assurance_history_replay_markdown", "verify_decision_assurance_history", "verify_decision_assurance_history_replay", "write_decision_assurance_history"]
