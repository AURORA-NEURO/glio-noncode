"""Track longitudinal assurance gates for review decision ledger snapshots.

This module records a sequence of already verified assurance-gate bundles.  It
does not make a later snapshot authoritative merely because it is newer: every
entry retains the source ledger, independent assurance, and release-gate
addresses that were observed at that point.  The history is append-only,
content-addressed, deterministic, and safe to project across the public
boundary.

The history package contains exactly ``manifest.json``, ``history.json``, and
``entries.json``.  History diffs contain exactly ``manifest.json`` and
``diff.json``.  No file path, private identity, execution-language attribute,
timestamp, or credential is included in any public record.
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
    assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance as assurance_model,
)
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

DecisionLedgerAssuranceGate = assurance_model.DecisionLedgerAssuranceGate

VERSION = assurance_model.VERSION + "-history-v1"
BOUNDARY = "public_release_registry_federation_gate_review_decision_ledger_assurance_history"
HISTORY_PREFIX = assurance_model.ASSURANCE_PREFIX + "-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
QUERY_PREFIX = HISTORY_PREFIX + "-query"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
DIFF_PREFIX = HISTORY_PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
DIFF_QUERY_PREFIX = DIFF_PREFIX + "-query"
DIFF_MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"

MANIFEST_NAME = "manifest.json"
HISTORY_NAME = "history.json"
ENTRIES_NAME = "entries.json"
DIFF_NAME = "diff.json"
FILES = (MANIFEST_NAME, HISTORY_NAME, ENTRIES_NAME)
DIFF_FILES = (MANIFEST_NAME, DIFF_NAME)

DEFAULT_HISTORY_ID = "glio-noncode-release-registry-federation-gate-review-decision-ledger-assurance-history"
DEFAULT_DIFF_ID = "glio-noncode-release-registry-federation-gate-review-decision-ledger-assurance-history-diff"
INITIAL_HEAD = "none:assurance-history-head"
NO_RECORD = "none:assurance-history-record"
MAX_ENTRIES = 4096
MAX_DIFF_ITEMS = MAX_ENTRIES * 2
MAX_QUERY_ITEMS = 4096
DEFAULT_LIMIT = 50

_FORBIDDEN_KEYS = frozenset({"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"})


class HistoryState(StrEnum):
    EMPTY = "empty"
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"


class HistoryTransition(StrEnum):
    INITIAL = "initial"
    STABLE = "stable"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    CHANGED = "changed"


class HistoryDiffAction(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class HistoryDiffDirection(StrEnum):
    UNCHANGED = "unchanged"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    MIXED = "mixed"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 4096)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    return None if value is None else _address(value, field)


def _optional_text(value: Any, field: str, maximum: int = 4096) -> str | None:
    return None if value is None else _text(value, field, maximum)


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} must be a bounded integer")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} has unknown fields: {','.join(sorted(unknown))}")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        if any(str(key).lower() in _FORBIDDEN_KEYS for key in value):
            return False
        return all(_public(key) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "c:\\" not in lowered and "/users/" not in lowered and "\\users\\" not in lowered
    return True


def _enum(value: Any, enum_type: type[StrEnum], field: str) -> str:
    value = _text(value, field, 128)
    if value not in {item.value for item in enum_type}:
        raise ValidationError(f"{field} is not supported")
    return value


def _gate_state(value: Any, field: str = "gate state") -> str:
    return _enum(value, assurance_model.GateState, field)


def _assurance_state(value: Any, field: str = "assurance state") -> str:
    return _enum(value, assurance_model.AssuranceState, field)


def _transition(value: Any, field: str = "history transition") -> str:
    return _enum(value, HistoryTransition, field)


def _action(value: Any, field: str = "history diff action") -> str:
    return _enum(value, HistoryDiffAction, field)


def _direction(value: Any, field: str = "history diff direction") -> str:
    return _enum(value, HistoryDiffDirection, field)


def _state(value: Any, field: str = "history state") -> str:
    return _enum(value, HistoryState, field)


def _optional_gate_state(value: Any, field: str = "candidate gate state") -> str | None:
    return None if value is None else _gate_state(value, field)


def _optional_assurance_state(value: Any, field: str = "candidate assurance state") -> str | None:
    return None if value is None else _assurance_state(value, field)


def _optional_bool(value: Any, field: str) -> bool | None:
    return None if value is None else _bool(value, field)


def _optional_count(value: Any, field: str) -> int | None:
    return None if value is None else _count(value, field, assurance_model.MAX_FINDINGS + assurance_model.MAX_CHECKS)


def _transition_counts(entries: Sequence[AssuranceHistoryEntry]) -> dict[str, int]:
    return {item.value: sum(entry.transition == item.value for entry in entries) for item in HistoryTransition}


def _state_counts(entries: Sequence[AssuranceHistoryEntry]) -> dict[str, int]:
    return {item.value: sum(entry.gate_state == item.value for entry in entries) for item in assurance_model.GateState}


def _quality_vector(entry: AssuranceHistoryEntry) -> tuple[int, ...]:
    """Return a stable quality ordering where larger is better."""
    state_score = {assurance_model.GateState.BLOCK.value: 0, assurance_model.GateState.HOLD.value: 1, assurance_model.GateState.PROMOTE.value: 2}
    return (
        int(entry.release_ready),
        int(entry.accepted),
        state_score[entry.gate_state],
        -entry.blocker_finding_count,
        -entry.warning_finding_count,
        -entry.blocker_check_count,
        -entry.warning_check_count,
        entry.passed_finding_count,
        entry.passed_check_count,
    )


def _entry_core(entry: AssuranceHistoryEntry) -> tuple[Any, ...]:
    return (
        entry.ledger_id,
        entry.ledger_address,
        entry.assurance_address,
        entry.gate_address,
        entry.bundle_address,
        entry.assurance_state,
        entry.gate_state,
        entry.accepted,
        entry.release_ready,
        entry.finding_count,
        entry.passed_finding_count,
        entry.warning_finding_count,
        entry.blocker_finding_count,
        entry.check_count,
        entry.passed_check_count,
        entry.warning_check_count,
        entry.blocker_check_count,
    )


def _classify_transition(previous: AssuranceHistoryEntry | None, current: AssuranceHistoryEntry) -> str:
    if previous is None:
        return HistoryTransition.INITIAL.value
    if _entry_core(previous) == _entry_core(current):
        return HistoryTransition.STABLE.value
    before, after = _quality_vector(previous), _quality_vector(current)
    if after > before:
        return HistoryTransition.IMPROVED.value
    if after < before:
        return HistoryTransition.REGRESSED.value
    return HistoryTransition.CHANGED.value


class AssuranceHistoryEntry:
    """One immutable assurance-gate observation in history order."""

    def __init__(
        self,
        ordinal: int,
        snapshot_id: str,
        ledger_id: str,
        ledger_address: str,
        assurance_address: str,
        gate_address: str,
        bundle_address: str,
        assurance_state: str,
        gate_state: str,
        accepted: bool,
        release_ready: bool,
        finding_count: int,
        passed_finding_count: int,
        warning_finding_count: int,
        blocker_finding_count: int,
        check_count: int,
        passed_check_count: int,
        warning_check_count: int,
        blocker_check_count: int,
        transition: str,
        previous_address: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.snapshot_id = snapshot_id
        self.ledger_id = ledger_id
        self.ledger_address = ledger_address
        self.assurance_address = assurance_address
        self.gate_address = gate_address
        self.bundle_address = bundle_address
        self.assurance_state = assurance_state
        self.gate_state = gate_state
        self.accepted = accepted
        self.release_ready = release_ready
        self.finding_count = finding_count
        self.passed_finding_count = passed_finding_count
        self.warning_finding_count = warning_finding_count
        self.blocker_finding_count = blocker_finding_count
        self.check_count = check_count
        self.passed_check_count = passed_check_count
        self.warning_check_count = warning_check_count
        self.blocker_check_count = blocker_check_count
        self.transition = transition
        self.previous_address = previous_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "history entry ordinal", MAX_ENTRIES - 1)
        _text(self.snapshot_id, "history snapshot ID", 512)
        _text(self.ledger_id, "history ledger ID", 512)
        for value, field in ((self.ledger_address, "history ledger address"), (self.assurance_address, "history assurance address"), (self.gate_address, "history gate address"), (self.bundle_address, "history bundle address"), (self.previous_address, "history previous address"), (self.content_address, "history entry address")):
            _address(value, field)
        _assurance_state(self.assurance_state)
        _gate_state(self.gate_state)
        _bool(self.accepted, "history entry accepted")
        _bool(self.release_ready, "history entry release-ready")
        _count(self.finding_count, "history finding count", assurance_model.MAX_FINDINGS, positive=True)
        _count(self.passed_finding_count, "history passed finding count", assurance_model.MAX_FINDINGS)
        _count(self.warning_finding_count, "history warning finding count", assurance_model.MAX_FINDINGS)
        _count(self.blocker_finding_count, "history blocker finding count", assurance_model.MAX_FINDINGS)
        _count(self.check_count, "history check count", assurance_model.MAX_CHECKS, positive=True)
        _count(self.passed_check_count, "history passed check count", assurance_model.MAX_CHECKS)
        _count(self.warning_check_count, "history warning check count", assurance_model.MAX_CHECKS)
        _count(self.blocker_check_count, "history blocker check count", assurance_model.MAX_CHECKS)
        if self.passed_finding_count + self.warning_finding_count + self.blocker_finding_count != self.finding_count:
            raise ValidationError("history finding counts are not conserved")
        if self.passed_check_count + self.warning_check_count + self.blocker_check_count != self.check_count:
            raise ValidationError("history check counts are not conserved")
        _transition(self.transition)
        if not _public(self.to_dict()):
            raise ValidationError("history entry crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_entry(self) != self.content_address:
            raise ValidationError("history entry address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "snapshot_id": self.snapshot_id,
            "ledger_id": self.ledger_id,
            "ledger_address": self.ledger_address,
            "assurance_address": self.assurance_address,
            "gate_address": self.gate_address,
            "bundle_address": self.bundle_address,
            "assurance_state": self.assurance_state,
            "gate_state": self.gate_state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "finding_count": self.finding_count,
            "passed_finding_count": self.passed_finding_count,
            "warning_finding_count": self.warning_finding_count,
            "blocker_finding_count": self.blocker_finding_count,
            "check_count": self.check_count,
            "passed_check_count": self.passed_check_count,
            "warning_check_count": self.warning_check_count,
            "blocker_check_count": self.blocker_check_count,
            "transition": self.transition,
            "previous_address": self.previous_address,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("ordinal", "snapshot_id", "ledger_id", "gate_state", "accepted", "release_ready", "transition", "content_address")}


def address_entry(value: AssuranceHistoryEntry) -> str:
    if not isinstance(value, AssuranceHistoryEntry):
        raise ValidationError("history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class AssuranceHistory:
    """Append-only history of independent assurance-gate snapshots."""

    def __init__(
        self,
        history_id: str,
        version: str,
        boundary: str,
        entry_count: int,
        head_address: str,
        state: str,
        latest_snapshot_id: str | None,
        latest_gate_address: str | None,
        accepted: bool,
        release_ready: bool,
        initial_count: int,
        stable_count: int,
        improved_count: int,
        regressed_count: int,
        changed_count: int,
        promote_count: int,
        hold_count: int,
        block_count: int,
        entries: Sequence[AssuranceHistoryEntry],
        content_address: str,
    ) -> None:
        self.history_id = history_id
        self.version = version
        self.boundary = boundary
        self.entry_count = entry_count
        self.head_address = head_address
        self.state = state
        self.latest_snapshot_id = latest_snapshot_id
        self.latest_gate_address = latest_gate_address
        self.accepted = accepted
        self.release_ready = release_ready
        self.initial_count = initial_count
        self.stable_count = stable_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.changed_count = changed_count
        self.promote_count = promote_count
        self.hold_count = hold_count
        self.block_count = block_count
        self.entries = tuple(entries)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.history_id, "history ID", 512)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("assurance history contract is invalid")
        _count(self.entry_count, "history entry count", MAX_ENTRIES)
        if self.entry_count != len(self.entries):
            raise ValidationError("history entry count is not conserved")
        _address(self.head_address, "history head address")
        _state(self.state)
        _optional_text(self.latest_snapshot_id, "latest snapshot ID", 512)
        _optional_address(self.latest_gate_address, "latest gate address")
        _bool(self.accepted, "history accepted")
        _bool(self.release_ready, "history release-ready")
        counters = ((self.initial_count, "initial count"), (self.stable_count, "stable count"), (self.improved_count, "improved count"), (self.regressed_count, "regressed count"), (self.changed_count, "changed count"), (self.promote_count, "promote count"), (self.hold_count, "hold count"), (self.block_count, "block count"))
        for value, field in counters:
            _count(value, field, MAX_ENTRIES)
        if sum(value for value, _ in counters[:5]) != self.entry_count:
            raise ValidationError("history transition counts are not conserved")
        if sum(value for value, _ in counters[5:]) != self.entry_count:
            raise ValidationError("history state counts are not conserved")
        ordinals = tuple(entry.ordinal for entry in self.entries)
        if ordinals != tuple(range(self.entry_count)):
            raise ValidationError("history entry ordinals are not contiguous")
        if len({entry.snapshot_id for entry in self.entries}) != self.entry_count:
            raise ValidationError("history snapshot IDs are not unique")
        if len({entry.content_address for entry in self.entries}) != self.entry_count:
            raise ValidationError("history entry addresses are not unique")
        for ordinal, entry in enumerate(self.entries):
            if entry.previous_address != (INITIAL_HEAD if ordinal == 0 else self.entries[ordinal - 1].content_address):
                raise ValidationError("history entry ancestry is not contiguous")
        expected_head = INITIAL_HEAD if not self.entries else self.entries[-1].content_address
        if self.head_address != expected_head:
            raise ValidationError("history head address is not terminal")
        if not self.entries:
            if self.state != HistoryState.EMPTY.value or self.latest_snapshot_id is not None or self.latest_gate_address is not None or self.accepted or self.release_ready:
                raise ValidationError("empty history summary is invalid")
        else:
            latest = self.entries[-1]
            if self.state != latest.gate_state or self.latest_snapshot_id != latest.snapshot_id or self.latest_gate_address != latest.gate_address or self.accepted != latest.accepted or self.release_ready != latest.release_ready:
                raise ValidationError("history summary does not match terminal entry")
        if not _public(self.to_dict()):
            raise ValidationError("history crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_history(self) != self.content_address:
            raise ValidationError("history address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "version": self.version,
            "boundary": self.boundary,
            "entry_count": self.entry_count,
            "head_address": self.head_address,
            "state": self.state,
            "latest_snapshot_id": self.latest_snapshot_id,
            "latest_gate_address": self.latest_gate_address,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "initial_count": self.initial_count,
            "stable_count": self.stable_count,
            "improved_count": self.improved_count,
            "regressed_count": self.regressed_count,
            "changed_count": self.changed_count,
            "promote_count": self.promote_count,
            "hold_count": self.hold_count,
            "block_count": self.block_count,
            "entries": tuple(entry.to_dict() for entry in self.entries),
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("history_id", "entry_count", "head_address", "state", "latest_snapshot_id", "latest_gate_address", "accepted", "release_ready", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count", "content_address")}


def address_history(value: AssuranceHistory) -> str:
    if not isinstance(value, AssuranceHistory):
        raise ValidationError("history address requires a typed history")
    body = value.to_dict() | {"entries": tuple(entry.to_dict() for entry in value.entries), "content_address": None}
    return content_hash(body, prefix=HISTORY_PREFIX)


def _snapshot_id(gate: DecisionLedgerAssuranceGate) -> str:
    digest = gate.content_address.rsplit(":", 1)[-1]
    return f"{gate.gate.ledger_id}:snapshot:{digest[:24]}"


def _entry_from_gate(gate: DecisionLedgerAssuranceGate, ordinal: int, snapshot_id: str, previous_address: str, transition: str) -> AssuranceHistoryEntry:
    assurance = gate.assurance
    release_gate = gate.gate
    body = {
        "ordinal": ordinal,
        "snapshot_id": _text(snapshot_id, "history snapshot ID", 512),
        "ledger_id": assurance.ledger_id,
        "ledger_address": assurance.ledger_address,
        "assurance_address": assurance.content_address,
        "gate_address": release_gate.content_address,
        "bundle_address": gate.content_address,
        "assurance_state": assurance.state,
        "gate_state": release_gate.state,
        "accepted": release_gate.accepted,
        "release_ready": release_gate.release_ready,
        "finding_count": assurance.finding_count,
        "passed_finding_count": assurance.passed_count,
        "warning_finding_count": assurance.warning_count,
        "blocker_finding_count": assurance.blocker_count,
        "check_count": release_gate.check_count,
        "passed_check_count": release_gate.passed_count,
        "warning_check_count": release_gate.warning_count,
        "blocker_check_count": release_gate.blocker_count,
        "transition": transition,
        "previous_address": previous_address,
    }
    provisional = AssuranceHistoryEntry(**body, content_address="pending:entry")
    return AssuranceHistoryEntry(**body, content_address=address_entry(provisional))


def _build_history_body(history_id: str, entries: Sequence[AssuranceHistoryEntry]) -> dict[str, Any]:
    entries = tuple(entries)
    transition_counts = _transition_counts(entries)
    state_counts = _state_counts(entries)
    latest = entries[-1] if entries else None
    return {
        "history_id": _text(history_id, "history ID", 512),
        "version": VERSION,
        "boundary": BOUNDARY,
        "entry_count": len(entries),
        "head_address": INITIAL_HEAD if not entries else entries[-1].content_address,
        "state": HistoryState.EMPTY.value if latest is None else latest.gate_state,
        "latest_snapshot_id": None if latest is None else latest.snapshot_id,
        "latest_gate_address": None if latest is None else latest.gate_address,
        "accepted": False if latest is None else latest.accepted,
        "release_ready": False if latest is None else latest.release_ready,
        "initial_count": transition_counts[HistoryTransition.INITIAL.value],
        "stable_count": transition_counts[HistoryTransition.STABLE.value],
        "improved_count": transition_counts[HistoryTransition.IMPROVED.value],
        "regressed_count": transition_counts[HistoryTransition.REGRESSED.value],
        "changed_count": transition_counts[HistoryTransition.CHANGED.value],
        "promote_count": state_counts[assurance_model.GateState.PROMOTE.value],
        "hold_count": state_counts[assurance_model.GateState.HOLD.value],
        "block_count": state_counts[assurance_model.GateState.BLOCK.value],
        "entries": tuple(entries),
    }


def _finish_history(history_id: str, entries: Sequence[AssuranceHistoryEntry]) -> AssuranceHistory:
    body = _build_history_body(history_id, entries)
    provisional = AssuranceHistory(**body, content_address="pending:history")
    body["content_address"] = address_history(provisional)
    return AssuranceHistory(**body)


def build_history(gates: Sequence[DecisionLedgerAssuranceGate] = (), *, history_id: str = DEFAULT_HISTORY_ID, snapshot_ids: Sequence[str] = ()) -> AssuranceHistory:
    gates = _sequence(gates, "assurance history gates", MAX_ENTRIES)
    snapshot_ids = _sequence(snapshot_ids, "assurance history snapshot IDs", MAX_ENTRIES)
    if snapshot_ids and len(snapshot_ids) != len(gates):
        raise ValidationError("snapshot ID count must equal gate count")
    entries: list[AssuranceHistoryEntry] = []
    for ordinal, gate in enumerate(gates):
        if not isinstance(gate, DecisionLedgerAssuranceGate):
            raise ValidationError("assurance history requires typed assurance gates")
        assurance_model.verify_assurance_gate(gate)
        snapshot_id = snapshot_ids[ordinal] if snapshot_ids else _snapshot_id(gate)
        if any(entry.snapshot_id == snapshot_id for entry in entries):
            raise ValidationError("assurance history snapshot IDs must be unique")
        previous = entries[-1] if entries else None
        provisional = _entry_from_gate(gate, ordinal, snapshot_id, INITIAL_HEAD if previous is None else previous.content_address, HistoryTransition.INITIAL.value)
        transition = _classify_transition(previous, provisional)
        entries.append(_entry_from_gate(gate, ordinal, snapshot_id, INITIAL_HEAD if previous is None else previous.content_address, transition))
    return _finish_history(history_id, entries)


def append_history(history: AssuranceHistory, gate: DecisionLedgerAssuranceGate, *, snapshot_id: str | None = None, expected_address: str | None = None) -> AssuranceHistory:
    verify_history(history)
    if not isinstance(gate, DecisionLedgerAssuranceGate):
        raise ValidationError("assurance history append requires a typed assurance gate")
    assurance_model.verify_assurance_gate(gate)
    if expected_address is not None and expected_address != history.content_address:
        raise ValidationError("assurance history expected head does not match")
    if history.entry_count >= MAX_ENTRIES:
        raise ValidationError("assurance history is at capacity")
    resolved_id = _snapshot_id(gate) if snapshot_id is None else _text(snapshot_id, "history snapshot ID", 512)
    if resolved_id in {entry.snapshot_id for entry in history.entries}:
        raise ValidationError("assurance history snapshot ID already exists")
    previous = history.entries[-1] if history.entries else None
    provisional = _entry_from_gate(gate, history.entry_count, resolved_id, history.head_address, HistoryTransition.INITIAL.value)
    transition = _classify_transition(previous, provisional)
    entry = _entry_from_gate(gate, history.entry_count, resolved_id, history.head_address, transition)
    return _finish_history(history.history_id, history.entries + (entry,))


def verify_history(value: AssuranceHistory) -> AssuranceHistory:
    if not isinstance(value, AssuranceHistory):
        raise ValidationError("assurance history verification requires a typed history")
    value._validate()
    expected = _finish_history(value.history_id, value.entries)
    if expected.to_dict() != value.to_dict():
        raise ValidationError("assurance history replay does not reproduce the stored summary")
    return value


def verify_history_against_gates(value: AssuranceHistory, gates: Sequence[DecisionLedgerAssuranceGate]) -> AssuranceHistory:
    verify_history(value)
    gates = _sequence(gates, "assurance history verification gates", MAX_ENTRIES)
    if len(gates) != value.entry_count:
        raise ValidationError("assurance history gate count does not match entries")
    snapshot_ids = tuple(entry.snapshot_id for entry in value.entries)
    expected = build_history(gates, history_id=value.history_id, snapshot_ids=snapshot_ids)
    if expected.to_dict() != value.to_dict():
        raise ValidationError("assurance history does not match the supplied gate sequence")
    return value


def entry_from_mapping(value: Mapping[str, Any]) -> AssuranceHistoryEntry:
    value = _mapping(value, "history entry")
    allowed = {"ordinal", "snapshot_id", "ledger_id", "ledger_address", "assurance_address", "gate_address", "bundle_address", "assurance_state", "gate_state", "accepted", "release_ready", "finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count", "transition", "previous_address", "content_address"}
    _strict(value, allowed, "history entry")
    return AssuranceHistoryEntry(**{key: value[key] for key in allowed})


def history_from_mapping(value: Mapping[str, Any]) -> AssuranceHistory:
    value = _mapping(value, "assurance history")
    allowed = {"history_id", "version", "boundary", "entry_count", "head_address", "state", "latest_snapshot_id", "latest_gate_address", "accepted", "release_ready", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count", "entries", "content_address"}
    _strict(value, allowed, "assurance history")
    entries = tuple(entry_from_mapping(item) for item in _sequence(value.get("entries"), "history entries", MAX_ENTRIES))
    body = dict(value)
    body["entries"] = entries
    return AssuranceHistory(**body)


class AssuranceHistoryDiffItem:
    """One stable-key comparison between two history snapshots."""

    def __init__(self, ordinal: int, key: str, action: str, direction: str, baseline_address: str | None, candidate_address: str | None, baseline_gate_state: str | None, candidate_gate_state: str | None, baseline_assurance_state: str | None, candidate_assurance_state: str | None, baseline_release_ready: bool | None, candidate_release_ready: bool | None, baseline_blocker_count: int | None, candidate_blocker_count: int | None, baseline_transition: str | None, candidate_transition: str | None, detail: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.key = key
        self.action = action
        self.direction = direction
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.baseline_gate_state = baseline_gate_state
        self.candidate_gate_state = candidate_gate_state
        self.baseline_assurance_state = baseline_assurance_state
        self.candidate_assurance_state = candidate_assurance_state
        self.baseline_release_ready = baseline_release_ready
        self.candidate_release_ready = candidate_release_ready
        self.baseline_blocker_count = baseline_blocker_count
        self.candidate_blocker_count = candidate_blocker_count
        self.baseline_transition = baseline_transition
        self.candidate_transition = candidate_transition
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "history diff ordinal", MAX_DIFF_ITEMS - 1)
        _text(self.key, "history diff key", 512)
        _action(self.action)
        _direction(self.direction)
        _optional_address(self.baseline_address, "baseline history address")
        _optional_address(self.candidate_address, "candidate history address")
        _optional_gate_state(self.baseline_gate_state, "baseline gate state")
        _optional_gate_state(self.candidate_gate_state, "candidate gate state")
        _optional_assurance_state(self.baseline_assurance_state, "baseline assurance state")
        _optional_assurance_state(self.candidate_assurance_state, "candidate assurance state")
        _optional_bool(self.baseline_release_ready, "baseline release-ready")
        _optional_bool(self.candidate_release_ready, "candidate release-ready")
        if self.baseline_blocker_count is not None:
            _count(self.baseline_blocker_count, "baseline blocker count", assurance_model.MAX_FINDINGS)
        if self.candidate_blocker_count is not None:
            _count(self.candidate_blocker_count, "candidate blocker count", assurance_model.MAX_FINDINGS)
        if self.baseline_transition is not None:
            _transition(self.baseline_transition, "baseline transition")
        if self.candidate_transition is not None:
            _transition(self.candidate_transition, "candidate transition")
        _text(self.detail, "history diff detail", 2048)
        _address(self.content_address, "history diff item address")
        if self.action == HistoryDiffAction.ADDED.value and self.candidate_address is None:
            raise ValidationError("added history diff item requires candidate address")
        if self.action == HistoryDiffAction.REMOVED.value and self.baseline_address is None:
            raise ValidationError("removed history diff item requires baseline address")
        if self.action in {HistoryDiffAction.UNCHANGED.value, HistoryDiffAction.CHANGED.value} and (self.baseline_address is None or self.candidate_address is None):
            raise ValidationError("matched history diff item requires both addresses")
        if not _public(self.to_dict()):
            raise ValidationError("history diff item crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_diff_item(self) != self.content_address:
            raise ValidationError("history diff item address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "key": self.key, "action": self.action, "direction": self.direction, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "baseline_gate_state": self.baseline_gate_state, "candidate_gate_state": self.candidate_gate_state, "baseline_assurance_state": self.baseline_assurance_state, "candidate_assurance_state": self.candidate_assurance_state, "baseline_release_ready": self.baseline_release_ready, "candidate_release_ready": self.candidate_release_ready, "baseline_blocker_count": self.baseline_blocker_count, "candidate_blocker_count": self.candidate_blocker_count, "baseline_transition": self.baseline_transition, "candidate_transition": self.candidate_transition, "detail": self.detail, "content_address": self.content_address}


def address_diff_item(value: AssuranceHistoryDiffItem) -> str:
    if not isinstance(value, AssuranceHistoryDiffItem):
        raise ValidationError("history diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


def _record_from_entry(entry: AssuranceHistoryEntry) -> dict[str, Any]:
    return entry.to_dict()


def _direction_for(action: str, baseline: AssuranceHistoryEntry | None, candidate: AssuranceHistoryEntry | None) -> str:
    if action == HistoryDiffAction.UNCHANGED.value:
        return HistoryDiffDirection.UNCHANGED.value
    if baseline is None or candidate is None:
        return HistoryDiffDirection.IMPROVED.value if candidate is not None else HistoryDiffDirection.REGRESSED.value
    before, after = _quality_vector(baseline), _quality_vector(candidate)
    if after > before:
        return HistoryDiffDirection.IMPROVED.value
    if after < before:
        return HistoryDiffDirection.REGRESSED.value
    return HistoryDiffDirection.MIXED.value


def _diff_detail(action: str, baseline: AssuranceHistoryEntry | None, candidate: AssuranceHistoryEntry | None) -> str:
    if action == HistoryDiffAction.ADDED.value:
        return "snapshot exists only in the candidate history"
    if action == HistoryDiffAction.REMOVED.value:
        return "snapshot exists only in the baseline history"
    if baseline is None or candidate is None:
        return "history snapshot comparison is incomplete"
    if action == HistoryDiffAction.UNCHANGED.value:
        return "snapshot projection is unchanged"
    changed = [name for name, before, after in (("gate_state", baseline.gate_state, candidate.gate_state), ("release_ready", baseline.release_ready, candidate.release_ready), ("blocker_finding_count", baseline.blocker_finding_count, candidate.blocker_finding_count), ("transition", baseline.transition, candidate.transition)) if before != after]
    return "changed fields: " + (", ".join(changed) if changed else "addressed source projection")


def _build_diff_item(ordinal: int, key: str, action: str, baseline: AssuranceHistoryEntry | None, candidate: AssuranceHistoryEntry | None) -> AssuranceHistoryDiffItem:
    direction = _direction_for(action, baseline, candidate)
    body = {"ordinal": ordinal, "key": key, "action": action, "direction": direction, "baseline_address": None if baseline is None else baseline.content_address, "candidate_address": None if candidate is None else candidate.content_address, "baseline_gate_state": None if baseline is None else baseline.gate_state, "candidate_gate_state": None if candidate is None else candidate.gate_state, "baseline_assurance_state": None if baseline is None else baseline.assurance_state, "candidate_assurance_state": None if candidate is None else candidate.assurance_state, "baseline_release_ready": None if baseline is None else baseline.release_ready, "candidate_release_ready": None if candidate is None else candidate.release_ready, "baseline_blocker_count": None if baseline is None else baseline.blocker_finding_count, "candidate_blocker_count": None if candidate is None else candidate.blocker_finding_count, "baseline_transition": None if baseline is None else baseline.transition, "candidate_transition": None if candidate is None else candidate.transition, "detail": _diff_detail(action, baseline, candidate)}
    provisional = AssuranceHistoryDiffItem(**body, content_address="pending:diff-item")
    return AssuranceHistoryDiffItem(**body, content_address=address_diff_item(provisional))


class AssuranceHistoryDiff:
    """Addressed comparison of two verified assurance histories."""

    def __init__(self, diff_id: str, version: str, boundary: str, baseline_history_id: str, candidate_history_id: str, baseline_address: str, candidate_address: str, item_count: int, added_count: int, removed_count: int, unchanged_count: int, changed_count: int, improved_count: int, regressed_count: int, state: str, items: Sequence[AssuranceHistoryDiffItem], content_address: str) -> None:
        self.diff_id = diff_id
        self.version = version
        self.boundary = boundary
        self.baseline_history_id = baseline_history_id
        self.candidate_history_id = candidate_history_id
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.item_count = item_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.state = state
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "history diff ID", 512)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff contract is invalid")
        _text(self.baseline_history_id, "baseline history ID", 512)
        _text(self.candidate_history_id, "candidate history ID", 512)
        _address(self.baseline_address, "baseline history address")
        _address(self.candidate_address, "candidate history address")
        _count(self.item_count, "history diff item count", MAX_DIFF_ITEMS)
        if self.item_count != len(self.items):
            raise ValidationError("history diff item count is not conserved")
        for value, field in ((self.added_count, "added count"), (self.removed_count, "removed count"), (self.unchanged_count, "unchanged count"), (self.changed_count, "changed count"), (self.improved_count, "improved count"), (self.regressed_count, "regressed count")):
            _count(value, field, MAX_DIFF_ITEMS)
        if self.added_count + self.removed_count + self.unchanged_count + self.changed_count != self.item_count:
            raise ValidationError("history diff action counts are not conserved")
        if self.improved_count > self.item_count or self.regressed_count > self.item_count:
            raise ValidationError("history diff direction counts are invalid")
        _direction(self.state, "history diff state")
        ordinals = tuple(item.ordinal for item in self.items)
        if ordinals != tuple(range(self.item_count)):
            raise ValidationError("history diff ordinals are not contiguous")
        if len({item.key for item in self.items}) != self.item_count:
            raise ValidationError("history diff keys are not unique")
        if len({item.content_address for item in self.items}) != self.item_count:
            raise ValidationError("history diff item addresses are not unique")
        if not _public(self.to_dict()):
            raise ValidationError("history diff crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_diff(self) != self.content_address:
            raise ValidationError("history diff address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "baseline_history_id": self.baseline_history_id, "candidate_history_id": self.candidate_history_id, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "state": self.state, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("diff_id", "baseline_history_id", "candidate_history_id", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "state", "content_address")}


def address_diff(value: AssuranceHistoryDiff) -> str:
    if not isinstance(value, AssuranceHistoryDiff):
        raise ValidationError("history diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def build_diff(baseline: AssuranceHistory, candidate: AssuranceHistory, *, diff_id: str = DEFAULT_DIFF_ID) -> AssuranceHistoryDiff:
    verify_history(baseline)
    verify_history(candidate)
    before = {entry.snapshot_id: entry for entry in baseline.entries}
    after = {entry.snapshot_id: entry for entry in candidate.entries}
    keys = sorted(set(before) | set(after))
    items: list[AssuranceHistoryDiffItem] = []
    for ordinal, key in enumerate(keys):
        left, right = before.get(key), after.get(key)
        if left is None:
            action = HistoryDiffAction.ADDED.value
        elif right is None:
            action = HistoryDiffAction.REMOVED.value
        elif left.to_dict() == right.to_dict():
            action = HistoryDiffAction.UNCHANGED.value
        else:
            action = HistoryDiffAction.CHANGED.value
        items.append(_build_diff_item(ordinal, key, action, left, right))
    added = sum(item.action == HistoryDiffAction.ADDED.value for item in items)
    removed = sum(item.action == HistoryDiffAction.REMOVED.value for item in items)
    unchanged = sum(item.action == HistoryDiffAction.UNCHANGED.value for item in items)
    changed = sum(item.action == HistoryDiffAction.CHANGED.value for item in items)
    improved = sum(item.direction == HistoryDiffDirection.IMPROVED.value for item in items)
    regressed = sum(item.direction == HistoryDiffDirection.REGRESSED.value for item in items)
    if regressed and improved:
        state = HistoryDiffDirection.MIXED.value
    elif regressed:
        state = HistoryDiffDirection.REGRESSED.value
    elif improved:
        state = HistoryDiffDirection.IMPROVED.value
    elif changed:
        state = HistoryDiffDirection.MIXED.value
    else:
        state = HistoryDiffDirection.UNCHANGED.value
    body = {"diff_id": _text(diff_id, "history diff ID", 512), "version": VERSION, "boundary": BOUNDARY, "baseline_history_id": baseline.history_id, "candidate_history_id": candidate.history_id, "baseline_address": baseline.content_address, "candidate_address": candidate.content_address, "item_count": len(items), "added_count": added, "removed_count": removed, "unchanged_count": unchanged, "changed_count": changed, "improved_count": improved, "regressed_count": regressed, "state": state, "items": tuple(items)}
    provisional = AssuranceHistoryDiff(**body, content_address="pending:diff")
    body["content_address"] = address_diff(provisional)
    return AssuranceHistoryDiff(**body)


def verify_diff(value: AssuranceHistoryDiff) -> AssuranceHistoryDiff:
    if not isinstance(value, AssuranceHistoryDiff):
        raise ValidationError("history diff verification requires a typed diff")
    value._validate()
    return value


def verify_diff_against_histories(value: AssuranceHistoryDiff, baseline: AssuranceHistory, candidate: AssuranceHistory) -> AssuranceHistoryDiff:
    verify_diff(value)
    expected = build_diff(baseline, candidate, diff_id=value.diff_id)
    if expected.to_dict() != value.to_dict():
        raise ValidationError("history diff does not match supplied histories")
    return value


def diff_item_from_mapping(value: Mapping[str, Any]) -> AssuranceHistoryDiffItem:
    value = _mapping(value, "history diff item")
    allowed = {"ordinal", "key", "action", "direction", "baseline_address", "candidate_address", "baseline_gate_state", "candidate_gate_state", "baseline_assurance_state", "candidate_assurance_state", "baseline_release_ready", "candidate_release_ready", "baseline_blocker_count", "candidate_blocker_count", "baseline_transition", "candidate_transition", "detail", "content_address"}
    _strict(value, allowed, "history diff item")
    return AssuranceHistoryDiffItem(**{key: value[key] for key in allowed})


def diff_from_mapping(value: Mapping[str, Any]) -> AssuranceHistoryDiff:
    value = _mapping(value, "history diff")
    allowed = {"diff_id", "version", "boundary", "baseline_history_id", "candidate_history_id", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "state", "items", "content_address"}
    _strict(value, allowed, "history diff")
    body = dict(value)
    body["items"] = tuple(diff_item_from_mapping(item) for item in _sequence(value.get("items"), "history diff items", MAX_DIFF_ITEMS))
    return AssuranceHistoryDiff(**body)


class HistoryQuery:
    """Bounded filter for history entries and summary resources."""

    RESOURCES = ("summary", "entries", "transitions", "states")

    def __init__(self, resource: str = "summary", transition: str | None = None, gate_state: str | None = None, assurance_state: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "history query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("history query resource is not supported")
        self.transition = None if transition is None else _transition(transition)
        self.gate_state = None if gate_state is None else _gate_state(gate_state)
        self.assurance_state = None if assurance_state is None else _assurance_state(assurance_state)
        self.accepted = _optional_bool(accepted, "history query accepted")
        self.release_ready = _optional_bool(release_ready, "history query release-ready")
        self.text = None if text is None else _text(text, "history query text", 256)
        self.offset = _count(offset, "history query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "history query limit", MAX_QUERY_ITEMS, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "transition": self.transition, "gate_state": self.gate_state, "assurance_state": self.assurance_state, "accepted": self.accepted, "release_ready": self.release_ready, "text": self.text, "offset": self.offset, "limit": self.limit}


class HistoryQueryResult:
    """Addressed result of a bounded history query."""

    def __init__(self, history_id: str, history_address: str, query: HistoryQuery, total_count: int, returned_count: int, items: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.history_id = _text(history_id, "history query history ID", 512)
        self.history_address = _address(history_address, "history query history address")
        if not isinstance(query, HistoryQuery):
            raise ValidationError("history query result requires a typed query")
        self.query = query
        self.total_count = _count(total_count, "history query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "history query returned count", MAX_QUERY_ITEMS)
        self.items = tuple(dict(_mapping(item, "history query item")) for item in items)
        self.content_address = _address(content_address, "history query result address")
        if self.returned_count != len(self.items) or self.returned_count > self.total_count:
            raise ValidationError("history query counts are not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("history query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("history query result address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "history_address": self.history_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": self.items, "content_address": self.content_address}


def address_query(value: HistoryQueryResult) -> str:
    if not isinstance(value, HistoryQueryResult):
        raise ValidationError("history query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _matches_entry(entry: AssuranceHistoryEntry, query: HistoryQuery) -> bool:
    if query.transition is not None and entry.transition != query.transition:
        return False
    if query.gate_state is not None and entry.gate_state != query.gate_state:
        return False
    if query.assurance_state is not None and entry.assurance_state != query.assurance_state:
        return False
    if query.accepted is not None and entry.accepted != query.accepted:
        return False
    if query.release_ready is not None and entry.release_ready != query.release_ready:
        return False
    if query.text is not None:
        haystack = canonical_json(entry.to_dict()).lower()
        if query.text.lower() not in haystack:
            return False
    return True


def query_history(value: AssuranceHistory, query: HistoryQuery | None = None, **kwargs: Any) -> HistoryQueryResult:
    verify_history(value)
    if query is not None and kwargs:
        raise ValidationError("history query object and keyword filters are mutually exclusive")
    resolved = query if query is not None else HistoryQuery(**kwargs)
    if resolved.resource == "summary":
        rows = (value.summary(),)
    else:
        matched = tuple(entry.to_dict() for entry in value.entries if _matches_entry(entry, resolved))
        if resolved.resource == "transitions":
            matched = tuple(item for item in matched if item["transition"] != HistoryTransition.STABLE.value)
        elif resolved.resource == "states":
            matched = tuple(item for item in matched if item["gate_state"] in {assurance_model.GateState.PROMOTE.value, assurance_model.GateState.HOLD.value, assurance_model.GateState.BLOCK.value})
        rows = matched
    total = len(rows)
    selected = rows[resolved.offset : resolved.offset + resolved.limit]
    pending = HistoryQueryResult(value.history_id, value.content_address, resolved, total, len(selected), selected, "pending:query")
    return HistoryQueryResult(value.history_id, value.content_address, resolved, total, len(selected), selected, address_query(pending))


class HistoryDiffQuery:
    """Bounded filter for history diff items."""

    RESOURCES = ("summary", "items", "changes", "directions")

    def __init__(self, resource: str = "summary", action: str | None = None, direction: str | None = None, gate_state: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "history diff query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("history diff query resource is not supported")
        self.action = None if action is None else _action(action)
        self.direction = None if direction is None else _direction(direction)
        self.gate_state = None if gate_state is None else _gate_state(gate_state)
        self.text = None if text is None else _text(text, "history diff query text", 256)
        self.offset = _count(offset, "history diff query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "history diff query limit", MAX_QUERY_ITEMS, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "action": self.action, "direction": self.direction, "gate_state": self.gate_state, "text": self.text, "offset": self.offset, "limit": self.limit}


class HistoryDiffQueryResult:
    """Addressed result of a bounded history diff query."""

    def __init__(self, diff_id: str, diff_address: str, query: HistoryDiffQuery, total_count: int, returned_count: int, items: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _text(diff_id, "history diff query diff ID", 512)
        self.diff_address = _address(diff_address, "history diff query diff address")
        if not isinstance(query, HistoryDiffQuery):
            raise ValidationError("history diff query result requires a typed query")
        self.query = query
        self.total_count = _count(total_count, "history diff query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "history diff query returned count", MAX_QUERY_ITEMS)
        self.items = tuple(dict(_mapping(item, "history diff query item")) for item in items)
        self.content_address = _address(content_address, "history diff query result address")
        if self.returned_count != len(self.items) or self.returned_count > self.total_count:
            raise ValidationError("history diff query counts are not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("history diff query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_diff_query(self) != self.content_address:
            raise ValidationError("history diff query result address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "diff_address": self.diff_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": self.items, "content_address": self.content_address}


def address_diff_query(value: HistoryDiffQueryResult) -> str:
    if not isinstance(value, HistoryDiffQueryResult):
        raise ValidationError("history diff query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_QUERY_PREFIX)


def _matches_diff_item(item: AssuranceHistoryDiffItem, query: HistoryDiffQuery) -> bool:
    if query.action is not None and item.action != query.action:
        return False
    if query.direction is not None and item.direction != query.direction:
        return False
    if query.gate_state is not None and item.candidate_gate_state != query.gate_state and item.baseline_gate_state != query.gate_state:
        return False
    if query.text is not None and query.text.lower() not in canonical_json(item.to_dict()).lower():
        return False
    return True


def query_diff(value: AssuranceHistoryDiff, query: HistoryDiffQuery | None = None, **kwargs: Any) -> HistoryDiffQueryResult:
    verify_diff(value)
    if query is not None and kwargs:
        raise ValidationError("history diff query object and keyword filters are mutually exclusive")
    resolved = query if query is not None else HistoryDiffQuery(**kwargs)
    if resolved.resource == "summary":
        rows = (value.summary(),)
    else:
        matched = tuple(item.to_dict() for item in value.items if _matches_diff_item(item, resolved))
        if resolved.resource == "changes":
            matched = tuple(item for item in matched if item["action"] == HistoryDiffAction.CHANGED.value)
        elif resolved.resource == "directions":
            matched = tuple(item for item in matched if item["direction"] != HistoryDiffDirection.UNCHANGED.value)
        rows = matched
    total = len(rows)
    selected = rows[resolved.offset : resolved.offset + resolved.limit]
    pending = HistoryDiffQueryResult(value.diff_id, value.content_address, resolved, total, len(selected), selected, "pending:diff-query")
    return HistoryDiffQueryResult(value.diff_id, value.content_address, resolved, total, len(selected), selected, address_diff_query(pending))


def history_json(value: AssuranceHistory) -> str:
    verify_history(value)
    return canonical_json(value.to_dict())


def entry_json(value: AssuranceHistoryEntry) -> str:
    if not isinstance(value, AssuranceHistoryEntry):
        raise ValidationError("history entry JSON requires a typed entry")
    value._validate()
    return canonical_json(value.to_dict())


def diff_json(value: AssuranceHistoryDiff) -> str:
    verify_diff(value)
    return canonical_json(value.to_dict())


def query_json(value: HistoryQueryResult) -> str:
    if not isinstance(value, HistoryQueryResult):
        raise ValidationError("history query JSON requires a typed result")
    return canonical_json(value.to_dict())


def diff_query_json(value: HistoryDiffQueryResult) -> str:
    if not isinstance(value, HistoryDiffQueryResult):
        raise ValidationError("history diff query JSON requires a typed result")
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field) for field in fields} for row in rows)
    return output.getvalue()


ENTRY_CSV_FIELDS = ("ordinal", "snapshot_id", "ledger_id", "ledger_address", "assurance_address", "gate_address", "bundle_address", "assurance_state", "gate_state", "accepted", "release_ready", "finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count", "transition", "previous_address", "content_address")
DIFF_CSV_FIELDS = ("ordinal", "key", "action", "direction", "baseline_address", "candidate_address", "baseline_gate_state", "candidate_gate_state", "baseline_assurance_state", "candidate_assurance_state", "baseline_release_ready", "candidate_release_ready", "baseline_blocker_count", "candidate_blocker_count", "baseline_transition", "candidate_transition", "detail", "content_address")


def history_csv(value: AssuranceHistory) -> str:
    verify_history(value)
    return _csv_text([entry.to_dict() for entry in value.entries], ENTRY_CSV_FIELDS)


def diff_csv(value: AssuranceHistoryDiff) -> str:
    verify_diff(value)
    return _csv_text([item.to_dict() for item in value.items], DIFF_CSV_FIELDS)


def query_csv(value: HistoryQueryResult) -> str:
    if not isinstance(value, HistoryQueryResult):
        raise ValidationError("history query CSV requires a typed result")
    if not value.items:
        return ""
    fields = tuple(sorted({key for row in value.items for key in row}))
    return _csv_text(value.items, fields)


def diff_query_csv(value: HistoryDiffQueryResult) -> str:
    if not isinstance(value, HistoryDiffQueryResult):
        raise ValidationError("history diff query CSV requires a typed result")
    if not value.items:
        return ""
    fields = tuple(sorted({key for row in value.items for key in row}))
    return _csv_text(value.items, fields)


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", ""]
    for key in sorted(summary):
        lines.append(f"- {key}: `{summary[key]}`")
    if rows:
        lines.extend(["", "## Records", "", "| ordinal | key | state | transition/action | direction | address |", "| ---: | --- | --- | --- | --- | --- |"])
        for row in rows:
            lines.append(f"| {row.get('ordinal', '')} | {row.get('snapshot_id', row.get('key', ''))} | {row.get('gate_state', row.get('candidate_gate_state', ''))} | {row.get('transition', row.get('action', ''))} | {row.get('direction', '')} | {row.get('content_address', '')} |")
    return "\n".join(lines) + "\n"


def render_history_markdown(value: AssuranceHistory) -> str:
    verify_history(value)
    return _markdown("Assurance History", value.summary(), [entry.summary() for entry in value.entries])


def render_entry_markdown(value: AssuranceHistoryEntry) -> str:
    if not isinstance(value, AssuranceHistoryEntry):
        raise ValidationError("history entry Markdown requires a typed entry")
    value._validate()
    return _markdown("Assurance History Entry", value.summary(), ())


def render_diff_markdown(value: AssuranceHistoryDiff) -> str:
    verify_diff(value)
    return _markdown("Assurance History Diff", value.summary(), [item.to_dict() for item in value.items])


def render_query_markdown(value: HistoryQueryResult) -> str:
    if not isinstance(value, HistoryQueryResult):
        raise ValidationError("history query Markdown requires a typed result")
    return _markdown("Assurance History Query", {"history_id": value.history_id, "history_address": value.history_address, "total_count": value.total_count, "returned_count": value.returned_count, "query": value.query.to_dict(), "content_address": value.content_address}, value.items)


def render_diff_query_markdown(value: HistoryDiffQueryResult) -> str:
    if not isinstance(value, HistoryDiffQueryResult):
        raise ValidationError("history diff query Markdown requires a typed result")
    return _markdown("Assurance History Diff Query", {"diff_id": value.diff_id, "diff_address": value.diff_address, "total_count": value.total_count, "returned_count": value.returned_count, "query": value.query.to_dict(), "content_address": value.content_address}, value.items)


def _string_schema(maximum: int = 4096) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": maximum}


def _address_schema() -> dict[str, Any]:
    return {"type": "string", "pattern": "^[^:]+:.+$", "minLength": 3, "maxLength": 4096}


def _nullable(schema: Mapping[str, Any]) -> dict[str, Any]:
    return {"anyOf": [dict(schema), {"type": "null"}]}


def _integer_schema(maximum: int) -> dict[str, Any]:
    return {"type": "integer", "minimum": 0, "maximum": maximum}


def _enum_schema(enum_type: type[StrEnum]) -> dict[str, Any]:
    return {"type": "string", "enum": [item.value for item in enum_type]}


def entry_schema() -> dict[str, Any]:
    properties = {"ordinal": _integer_schema(MAX_ENTRIES - 1), "snapshot_id": _string_schema(512), "ledger_id": _string_schema(512), "ledger_address": _address_schema(), "assurance_address": _address_schema(), "gate_address": _address_schema(), "bundle_address": _address_schema(), "assurance_state": _enum_schema(assurance_model.AssuranceState), "gate_state": _enum_schema(assurance_model.GateState), "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "finding_count": _integer_schema(assurance_model.MAX_FINDINGS), "passed_finding_count": _integer_schema(assurance_model.MAX_FINDINGS), "warning_finding_count": _integer_schema(assurance_model.MAX_FINDINGS), "blocker_finding_count": _integer_schema(assurance_model.MAX_FINDINGS), "check_count": _integer_schema(assurance_model.MAX_CHECKS), "passed_check_count": _integer_schema(assurance_model.MAX_CHECKS), "warning_check_count": _integer_schema(assurance_model.MAX_CHECKS), "blocker_check_count": _integer_schema(assurance_model.MAX_CHECKS), "transition": _enum_schema(HistoryTransition), "previous_address": _address_schema(), "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


def history_schema() -> dict[str, Any]:
    properties = {"history_id": _string_schema(512), "version": _string_schema(256), "boundary": _string_schema(256), "entry_count": _integer_schema(MAX_ENTRIES), "head_address": _address_schema(), "state": _enum_schema(HistoryState), "latest_snapshot_id": _nullable(_string_schema(512)), "latest_gate_address": _nullable(_address_schema()), "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "initial_count": _integer_schema(MAX_ENTRIES), "stable_count": _integer_schema(MAX_ENTRIES), "improved_count": _integer_schema(MAX_ENTRIES), "regressed_count": _integer_schema(MAX_ENTRIES), "changed_count": _integer_schema(MAX_ENTRIES), "promote_count": _integer_schema(MAX_ENTRIES), "hold_count": _integer_schema(MAX_ENTRIES), "block_count": _integer_schema(MAX_ENTRIES), "entries": {"type": "array", "maxItems": MAX_ENTRIES, "items": entry_schema()}, "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


def diff_item_schema() -> dict[str, Any]:
    properties = {"ordinal": _integer_schema(MAX_DIFF_ITEMS - 1), "key": _string_schema(512), "action": _enum_schema(HistoryDiffAction), "direction": _enum_schema(HistoryDiffDirection), "baseline_address": _nullable(_address_schema()), "candidate_address": _nullable(_address_schema()), "baseline_gate_state": _nullable(_enum_schema(assurance_model.GateState)), "candidate_gate_state": _nullable(_enum_schema(assurance_model.GateState)), "baseline_assurance_state": _nullable(_enum_schema(assurance_model.AssuranceState)), "candidate_assurance_state": _nullable(_enum_schema(assurance_model.AssuranceState)), "baseline_release_ready": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "candidate_release_ready": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "baseline_blocker_count": {"anyOf": [_integer_schema(assurance_model.MAX_FINDINGS), {"type": "null"}]}, "candidate_blocker_count": {"anyOf": [_integer_schema(assurance_model.MAX_FINDINGS), {"type": "null"}]}, "baseline_transition": _nullable(_enum_schema(HistoryTransition)), "candidate_transition": _nullable(_enum_schema(HistoryTransition)), "detail": _string_schema(2048), "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


def diff_schema() -> dict[str, Any]:
    properties = {"diff_id": _string_schema(512), "version": _string_schema(256), "boundary": _string_schema(256), "baseline_history_id": _string_schema(512), "candidate_history_id": _string_schema(512), "baseline_address": _address_schema(), "candidate_address": _address_schema(), "item_count": _integer_schema(MAX_DIFF_ITEMS), "added_count": _integer_schema(MAX_DIFF_ITEMS), "removed_count": _integer_schema(MAX_DIFF_ITEMS), "unchanged_count": _integer_schema(MAX_DIFF_ITEMS), "changed_count": _integer_schema(MAX_DIFF_ITEMS), "improved_count": _integer_schema(MAX_DIFF_ITEMS), "regressed_count": _integer_schema(MAX_DIFF_ITEMS), "state": _enum_schema(HistoryDiffDirection), "items": {"type": "array", "maxItems": MAX_DIFF_ITEMS, "items": diff_item_schema()}, "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


def query_schema() -> dict[str, Any]:
    properties = {"resource": {"type": "string", "enum": list(HistoryQuery.RESOURCES)}, "transition": _nullable(_enum_schema(HistoryTransition)), "gate_state": _nullable(_enum_schema(assurance_model.GateState)), "assurance_state": _nullable(_enum_schema(assurance_model.AssuranceState)), "accepted": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "release_ready": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "text": _nullable(_string_schema(256)), "offset": _integer_schema(MAX_QUERY_ITEMS), "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}}
    return {"type": "object", "additionalProperties": False, "required": ["resource", "transition", "gate_state", "assurance_state", "accepted", "release_ready", "text", "offset", "limit"], "properties": properties}


def diff_query_schema() -> dict[str, Any]:
    properties = {"resource": {"type": "string", "enum": list(HistoryDiffQuery.RESOURCES)}, "action": _nullable(_enum_schema(HistoryDiffAction)), "direction": _nullable(_enum_schema(HistoryDiffDirection)), "gate_state": _nullable(_enum_schema(assurance_model.GateState)), "text": _nullable(_string_schema(256)), "offset": _integer_schema(MAX_QUERY_ITEMS), "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}}
    return {"type": "object", "additionalProperties": False, "required": ["resource", "action", "direction", "gate_state", "text", "offset", "limit"], "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_files": list(FILES), "diff_package_files": list(DIFF_FILES), "max_entries": MAX_ENTRIES, "max_diff_items": MAX_DIFF_ITEMS, "resources": {"history": list(HistoryQuery.RESOURCES), "diff": list(HistoryDiffQuery.RESOURCES)}, "transitions": [item.value for item in HistoryTransition], "states": [item.value for item in HistoryState], "actions": [item.value for item in HistoryDiffAction], "directions": [item.value for item in HistoryDiffDirection], "features": ["append-only snapshots", "optimistic head guards", "independent replay", "stable-key history diffs", "bounded queries", "canonical JSON", "fixed-column CSV", "public Markdown", "exact-file persistence", "legacy-shape rejection"]}


def _history_storage(value: AssuranceHistory) -> tuple[bytes, bytes]:
    """Return summary and separately addressed entry bytes for persistence."""
    summary = value.to_dict()
    summary.pop("entries", None)
    entries = {"version": VERSION, "boundary": BOUNDARY, "history_id": value.history_id, "entry_count": value.entry_count, "entries": tuple(entry.to_dict() for entry in value.entries)}
    return canonical_bytes(summary), canonical_bytes(entries)


def _artifact(name: str, raw: bytes) -> dict[str, Any]:
    byte_address = hash_bytes(raw)
    return {"name": name, "bytes": len(raw), "byte_address": byte_address, "file_address": content_hash({"name": name, "byte_address": byte_address}, prefix=HISTORY_PREFIX + "-file")}


def _manifest_body(value: AssuranceHistory, history_raw: bytes, entries_raw: bytes) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "history_id": value.history_id, "history_address": value.content_address, "artifact_count": 2, "files": [HISTORY_NAME, ENTRIES_NAME], "artifacts": [_artifact(HISTORY_NAME, history_raw), _artifact(ENTRIES_NAME, entries_raw)], "manifest_address": None}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=MANIFEST_PREFIX)


def _diff_manifest_body(value: AssuranceHistoryDiff, raw: bytes) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_id": value.diff_id, "baseline_address": value.baseline_address, "candidate_address": value.candidate_address, "artifact_count": 1, "files": [DIFF_NAME], "artifact": _artifact(DIFF_NAME, raw), "manifest_address": None}


def _diff_manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=DIFF_MANIFEST_PREFIX)


def _write_exact(destination: Path, files: Mapping[str, bytes], *, overwrite: bool, prefix: str) -> Path:
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("history destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=prefix, dir=str(destination.parent)))
    try:
        for name, raw in files.items():
            (temporary / name).write_bytes(raw)
        if destination.exists():
            if not destination.is_dir() or not overwrite:
                raise ValidationError("history destination cannot be replaced")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def write_history(value: AssuranceHistory, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_history(value)
    destination = Path(directory)
    history_raw, entries_raw = _history_storage(value)
    manifest = _manifest_body(value, history_raw, entries_raw)
    manifest["manifest_address"] = _manifest_address(manifest)
    return _write_exact(destination, {HISTORY_NAME: history_raw, ENTRIES_NAME: entries_raw, MANIFEST_NAME: canonical_bytes(manifest)}, overwrite=overwrite, prefix=".gnd-history-")


def write_diff(value: AssuranceHistoryDiff, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_diff(value)
    destination = Path(directory)
    raw = canonical_bytes(value.to_dict())
    manifest = _diff_manifest_body(value, raw)
    manifest["manifest_address"] = _diff_manifest_address(manifest)
    return _write_exact(destination, {DIFF_NAME: raw, MANIFEST_NAME: canonical_bytes(manifest)}, overwrite=overwrite, prefix=".gnd-history-diff-")


def _read_json(path: Path, field: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{field} must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{field} is invalid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"{field} is not canonical JSON")
    return dict(_mapping(value, field))


def _artifact_by_name(manifest: Mapping[str, Any], name: str, field: str) -> Mapping[str, Any]:
    artifacts = _sequence(manifest.get("artifacts"), f"{field} artifacts", 2)
    matches = [item for item in artifacts if _mapping(item, f"{field} artifact").get("name") == name]
    if len(matches) != 1:
        raise ValidationError(f"{field} is missing exactly one {name} artifact")
    return _mapping(matches[0], f"{field} artifact")


def _verify_artifact(manifest: Mapping[str, Any], source: Path, name: str, field: str) -> bytes:
    artifact = _artifact_by_name(manifest, name, field)
    path = source / name
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{field} {name} must be a regular file")
    raw = path.read_bytes()
    expected = _artifact(name, raw)
    if dict(artifact) != expected:
        raise ValidationError(f"{field} {name} bytes are not addressed")
    return raw


def _verify_directory(source: Path, files: Sequence[str], field: str) -> Mapping[str, Any]:
    if source.is_symlink() or not source.is_dir():
        raise ValidationError(f"{field} directory must be a regular directory")
    if any(item.is_symlink() for item in source.iterdir()) or {item.name for item in source.iterdir()} != set(files):
        raise ValidationError(f"{field} file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, f"{field} manifest")
    return manifest


def load_history(directory: str | Path) -> AssuranceHistory:
    source = Path(directory)
    manifest = _verify_directory(source, FILES, "assurance history")
    allowed = {"version", "boundary", "history_id", "history_address", "artifact_count", "files", "artifacts", "manifest_address"}
    _strict(manifest, allowed, "assurance history manifest")
    if manifest.get("version") != VERSION or manifest.get("boundary") != BOUNDARY or manifest.get("artifact_count") != 2 or tuple(manifest.get("files", ())) != (HISTORY_NAME, ENTRIES_NAME) or manifest.get("manifest_address") != _manifest_address(dict(manifest) | {"manifest_address": None}):
        raise ValidationError("assurance history manifest contract is invalid")
    history_raw = _verify_artifact(manifest, source, HISTORY_NAME, "assurance history")
    entries_raw = _verify_artifact(manifest, source, ENTRIES_NAME, "assurance history")
    summary = _read_json(source / HISTORY_NAME, "assurance history summary")
    entries_document = _read_json(source / ENTRIES_NAME, "assurance history entries")
    _strict(summary, {"history_id", "version", "boundary", "entry_count", "head_address", "state", "latest_snapshot_id", "latest_gate_address", "accepted", "release_ready", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count", "content_address"}, "assurance history summary")
    _strict(entries_document, {"version", "boundary", "history_id", "entry_count", "entries"}, "assurance history entries")
    if entries_document.get("version") != VERSION or entries_document.get("boundary") != BOUNDARY or entries_document.get("history_id") != summary.get("history_id") or entries_document.get("entry_count") != summary.get("entry_count"):
        raise ValidationError("assurance history entries linkage is invalid")
    if manifest.get("history_id") != summary.get("history_id") or manifest.get("history_address") != summary.get("content_address"):
        raise ValidationError("assurance history manifest linkage is invalid")
    value = history_from_mapping(dict(summary) | {"entries": entries_document.get("entries")})
    if canonical_bytes(summary) != history_raw or canonical_bytes(entries_document) != entries_raw:
        raise ValidationError("assurance history artifact bytes are not canonical")
    return verify_history(value)


def load_diff(directory: str | Path) -> AssuranceHistoryDiff:
    source = Path(directory)
    manifest = _verify_directory(source, DIFF_FILES, "assurance history diff")
    allowed = {"version", "boundary", "diff_id", "baseline_address", "candidate_address", "artifact_count", "files", "artifact", "manifest_address"}
    _strict(manifest, allowed, "assurance history diff manifest")
    if manifest.get("version") != VERSION or manifest.get("boundary") != BOUNDARY or manifest.get("artifact_count") != 1 or tuple(manifest.get("files", ())) != (DIFF_NAME,) or manifest.get("manifest_address") != _diff_manifest_address(dict(manifest) | {"manifest_address": None}):
        raise ValidationError("assurance history diff manifest contract is invalid")
    raw = _verify_artifact({"artifacts": [manifest.get("artifact")]}, source, DIFF_NAME, "assurance history diff")
    value = diff_from_mapping(_read_json(source / DIFF_NAME, "assurance history diff"))
    if manifest.get("diff_id") != value.diff_id or manifest.get("baseline_address") != value.baseline_address or manifest.get("candidate_address") != value.candidate_address:
        raise ValidationError("assurance history diff manifest linkage is invalid")
    if canonical_bytes(value.to_dict()) != raw:
        raise ValidationError("assurance history diff artifact bytes are not canonical")
    return verify_diff(value)


def verify_history_directory(directory: str | Path) -> AssuranceHistory:
    return load_history(directory)


def verify_diff_directory(directory: str | Path) -> AssuranceHistoryDiff:
    return load_diff(directory)


__all__ = [
    "BOUNDARY",
    "DEFAULT_DIFF_ID",
    "DEFAULT_HISTORY_ID",
    "DIFF_FILES",
    "DIFF_NAME",
    "ENTRIES_NAME",
    "FILES",
    "HistoryDiffAction",
    "HistoryDiffDirection",
    "HistoryDiffQuery",
    "HistoryDiffQueryResult",
    "HistoryQuery",
    "HistoryQueryResult",
    "HistoryState",
    "HistoryTransition",
    "HISTORY_NAME",
    "INITIAL_HEAD",
    "MAX_DIFF_ITEMS",
    "MAX_ENTRIES",
    "MAX_QUERY_ITEMS",
    "NO_RECORD",
    "AssuranceHistory",
    "AssuranceHistoryDiff",
    "AssuranceHistoryDiffItem",
    "AssuranceHistoryEntry",
    "address_diff",
    "address_diff_item",
    "address_diff_query",
    "address_entry",
    "address_history",
    "append_history",
    "build_diff",
    "build_history",
    "capabilities",
    "diff_csv",
    "diff_from_mapping",
    "diff_item_from_mapping",
    "diff_item_schema",
    "diff_json",
    "diff_query_csv",
    "diff_query_json",
    "diff_query_schema",
    "diff_schema",
    "entry_from_mapping",
    "entry_json",
    "entry_schema",
    "history_csv",
    "history_from_mapping",
    "history_json",
    "history_schema",
    "load_diff",
    "load_history",
    "query_diff",
    "query_history",
    "query_json",
    "query_schema",
    "render_diff_markdown",
    "render_diff_query_markdown",
    "render_entry_markdown",
    "render_history_markdown",
    "render_query_markdown",
    "verify_diff",
    "verify_diff_against_histories",
    "verify_diff_directory",
    "verify_history",
    "verify_history_against_gates",
    "verify_history_directory",
    "write_diff",
    "write_history",
]
