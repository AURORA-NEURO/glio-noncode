"""Aggregate and compare independent decision-assurance histories.

The history contract records one ordered stream of assurance-gate observations.
This module adds the next analytical boundary: a deterministic series over
multiple histories.  A series is a public projection, never a source-of-truth
merge.  Each retained history remains independently addressed and can be
reloaded, replayed, queried, and compared without carrying paths, identities,
timestamps, runtime details, or private metadata.

Series packages contain exactly ``manifest.json``, ``series.json``, and
``entries.json``.  Canonical JSON, byte receipts, deterministic ordering,
conserved aggregate counters, and an independent replay report make the
package useful for downloaded-data demonstrations and repeatable CI checks.
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

from . import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history as history_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

DecisionAssuranceHistory = history_model.DecisionAssuranceHistory

VERSION = history_model.VERSION + "-series-v1"
BOUNDARY = "public_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series"
SERIES_PREFIX = history_model.HISTORY_PREFIX + "-series"
ENTRY_PREFIX = SERIES_PREFIX + "-entry"
DIFF_PREFIX = SERIES_PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
REPLAY_PREFIX = SERIES_PREFIX + "-replay"
REPLAY_CHECK_PREFIX = REPLAY_PREFIX + "-check"
QUERY_PREFIX = SERIES_PREFIX + "-query"
MANIFEST_PREFIX = SERIES_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
SERIES_NAME = "series.json"
ENTRIES_NAME = "entries.json"
FILES = (MANIFEST_NAME, SERIES_NAME, ENTRIES_NAME)
DEFAULT_SERIES_ID = "glio-noncode-observatory-registry-federation-review-decision-assurance-history-series"
MAX_HISTORIES = 256
MAX_QUERY_ITEMS = 4096
DEFAULT_LIMIT = 50

_FORBIDDEN_KEYS = frozenset({"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"})


class HistorySeriesState(StrEnum):
    """Projection of the current state across all retained histories."""

    EMPTY = "empty"
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    MIXED = "mixed"


class HistorySeriesChangeAction(StrEnum):
    """Membership or semantic outcome for one history in a diff."""

    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class HistorySeriesChangeDirection(StrEnum):
    """Directional interpretation of a changed history's terminal state."""

    UNCHANGED = "unchanged"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    CHANGED = "changed"


class HistorySeriesReplayState(StrEnum):
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
    if set(value) - allowed:
        raise ValidationError(f"{field} contains unknown fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in _FORBIDDEN_KEYS and _public(key) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _state(value: Any, field: str = "history series state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in HistorySeriesState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _history_state(value: Any, field: str = "history state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in history_model.AssuranceHistoryState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _gate_state(value: Any, field: str = "gate state") -> str:
    if value is None:
        raise ValidationError(f"{field} is required")
    value = _text(value, field, 32)
    if value not in {"promote", "hold", "block"}:
        raise ValidationError(f"{field} is invalid")
    return value


def _optional_gate_state(value: Any, field: str = "gate state") -> str | None:
    return None if value is None else _gate_state(value, field)


def _assurance_state(value: Any, field: str = "assurance state") -> str:
    value = _text(value, field, 32)
    if value not in {"passed", "warning", "blocked"}:
        raise ValidationError(f"{field} is invalid")
    return value


def _optional_assurance_state(value: Any, field: str = "assurance state") -> str | None:
    return None if value is None else _assurance_state(value, field)


def _transition_counts() -> dict[str, int]:
    return {item.value: 0 for item in history_model.AssuranceHistoryTransition}


def _state_counts() -> dict[str, int]:
    return {item.value: 0 for item in HistorySeriesState if item != HistorySeriesState.EMPTY}


def _score(state: str | None) -> int:
    return {None: -1, "block": 0, "hold": 1, "promote": 2}.get(state, -1)


class DecisionAssuranceHistorySeriesEntry:
    """One deterministic history summary retained by a series."""

    def __init__(self, ordinal: int, history_id: str, history_address: str, head_address: str | None, entry_count: int, initial_snapshot_id: str | None, current_snapshot_id: str | None, current_assurance_state: str | None, current_gate_state: str | None, current_state: str, current_accepted: bool, current_release_ready: bool, initial_count: int, stable_count: int, improved_count: int, regressed_count: int, changed_count: int, accepted_count: int, release_ready_count: int, content_address: str) -> None:
        self.ordinal = ordinal
        self.history_id = history_id
        self.history_address = history_address
        self.head_address = head_address
        self.entry_count = entry_count
        self.initial_snapshot_id = initial_snapshot_id
        self.current_snapshot_id = current_snapshot_id
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
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "history series entry ordinal", MAX_HISTORIES)
        _text(self.history_id, "series history ID", 256)
        _address(self.history_address, "series history address")
        _optional_address(self.head_address, "series history head address")
        _count(self.entry_count, "series retained observation count", history_model.MAX_ENTRIES)
        _text(self.initial_snapshot_id, "series initial snapshot ID", 256) if self.initial_snapshot_id is not None else None
        _text(self.current_snapshot_id, "series current snapshot ID", 256) if self.current_snapshot_id is not None else None
        _optional_assurance_state(self.current_assurance_state)
        _optional_gate_state(self.current_gate_state)
        _state(self.current_state)
        for value, field in ((self.current_accepted, "series current accepted"), (self.current_release_ready, "series current release readiness")):
            _bool(value, field)
        names = ("initial", "stable", "improved", "regressed", "changed")
        values = (self.initial_count, self.stable_count, self.improved_count, self.regressed_count, self.changed_count)
        for value, name in zip(values, names, strict=True):
            _count(value, f"series {name} transition count", history_model.MAX_ENTRIES)
        for value, name in ((self.accepted_count, "accepted"), (self.release_ready_count, "release-ready")):
            _count(value, f"series {name} observation count", history_model.MAX_ENTRIES)
        if sum(values) != self.entry_count or self.accepted_count > self.entry_count or self.release_ready_count > self.entry_count:
            raise ValidationError("series history counters are not conserved")
        if self.entry_count == 0:
            if any(value is not None for value in (self.head_address, self.initial_snapshot_id, self.current_snapshot_id, self.current_assurance_state, self.current_gate_state)) or self.current_state != HistorySeriesState.EMPTY.value or self.current_accepted or self.current_release_ready:
                raise ValidationError("empty series history projection is invalid")
        elif self.current_state == HistorySeriesState.EMPTY.value or any(value is None for value in (self.head_address, self.initial_snapshot_id, self.current_snapshot_id, self.current_assurance_state, self.current_gate_state)):
            raise ValidationError("non-empty series history projection is incomplete")
        _address(self.content_address, "series history entry address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_entry(self) != self.content_address:
            raise ValidationError("series history entry address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "history_id": self.history_id, "history_address": self.history_address, "head_address": self.head_address, "entry_count": self.entry_count, "initial_snapshot_id": self.initial_snapshot_id, "current_snapshot_id": self.current_snapshot_id, "current_assurance_state": self.current_assurance_state, "current_gate_state": self.current_gate_state, "current_state": self.current_state, "current_accepted": self.current_accepted, "current_release_ready": self.current_release_ready, "initial_count": self.initial_count, "stable_count": self.stable_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "changed_count": self.changed_count, "accepted_count": self.accepted_count, "release_ready_count": self.release_ready_count, "content_address": self.content_address}


def address_decision_assurance_history_series_entry(value: DecisionAssuranceHistorySeriesEntry) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def _entry_from_history(history: DecisionAssuranceHistory, ordinal: int) -> DecisionAssuranceHistorySeriesEntry:
    body = {"ordinal": ordinal, "history_id": history.history_id, "history_address": history.content_address, "head_address": history.head_address, "entry_count": history.entry_count, "initial_snapshot_id": history.initial_snapshot_id, "current_snapshot_id": history.current_snapshot_id, "current_assurance_state": history.current_assurance_state, "current_gate_state": history.current_gate_state, "current_state": history.current_state, "current_accepted": history.current_accepted, "current_release_ready": history.current_release_ready, "initial_count": history.initial_count, "stable_count": history.stable_count, "improved_count": history.improved_count, "regressed_count": history.regressed_count, "changed_count": history.changed_count, "accepted_count": history.accepted_count, "release_ready_count": history.release_ready_count, "content_address": "pending:series-entry"}
    provisional = DecisionAssuranceHistorySeriesEntry(**body)
    body["content_address"] = address_decision_assurance_history_series_entry(provisional)
    return DecisionAssuranceHistorySeriesEntry(**body)


class DecisionAssuranceHistorySeries:
    """Deterministically sorted aggregate over independently verified histories."""

    def __init__(self, series_id: str, version: str, boundary: str, history_count: int, observation_count: int, current_state: str, ready_history_count: int, held_history_count: int, blocked_history_count: int, empty_history_count: int, mixed_history_count: int, current_ready_count: int, current_held_count: int, current_blocked_count: int, current_accepted_count: int, current_release_ready_count: int, initial_count: int, stable_count: int, improved_count: int, regressed_count: int, changed_count: int, accepted_observation_count: int, release_ready_observation_count: int, entries: Sequence[DecisionAssuranceHistorySeriesEntry], content_address: str) -> None:
        self.series_id = series_id
        self.version = version
        self.boundary = boundary
        self.history_count = history_count
        self.observation_count = observation_count
        self.current_state = current_state
        self.ready_history_count = ready_history_count
        self.held_history_count = held_history_count
        self.blocked_history_count = blocked_history_count
        self.empty_history_count = empty_history_count
        self.mixed_history_count = mixed_history_count
        self.current_ready_count = current_ready_count
        self.current_held_count = current_held_count
        self.current_blocked_count = current_blocked_count
        self.current_accepted_count = current_accepted_count
        self.current_release_ready_count = current_release_ready_count
        self.initial_count = initial_count
        self.stable_count = stable_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.changed_count = changed_count
        self.accepted_observation_count = accepted_observation_count
        self.release_ready_observation_count = release_ready_observation_count
        self.entries = tuple(entries)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.series_id, "assurance history series ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("assurance history series contract is invalid")
        _count(self.history_count, "assurance history series count", MAX_HISTORIES)
        if self.history_count != len(self.entries):
            raise ValidationError("assurance history series count is not conserved")
        ids: list[str] = []
        state_counts = {item.value: 0 for item in HistorySeriesState}
        transition_counts = _transition_counts()
        aggregate_observations = 0
        aggregate_accepted = 0
        aggregate_release_ready = 0
        for ordinal, entry in enumerate(self.entries):
            if not isinstance(entry, DecisionAssuranceHistorySeriesEntry) or entry.ordinal != ordinal:
                raise ValidationError("assurance history series ordinals are not contiguous")
            if address_decision_assurance_history_series_entry(entry) != entry.content_address:
                raise ValidationError("assurance history series entry address mismatch")
            if entry.history_id in ids:
                raise ValidationError("assurance history IDs are not unique")
            ids.append(entry.history_id)
            if ids != sorted(ids):
                raise ValidationError("assurance history series entries are not sorted")
            state_counts[entry.current_state] += 1
            for name, value in zip(("initial", "stable", "improved", "regressed", "changed"), (entry.initial_count, entry.stable_count, entry.improved_count, entry.regressed_count, entry.changed_count), strict=True):
                transition_counts[name] += value
            aggregate_observations += entry.entry_count
            aggregate_accepted += entry.accepted_count
            aggregate_release_ready += entry.release_ready_count
        if self.observation_count != aggregate_observations or self.accepted_observation_count != aggregate_accepted or self.release_ready_observation_count != aggregate_release_ready:
            raise ValidationError("assurance history series observation counters are not conserved")
        for name, value in transition_counts.items():
            if value != getattr(self, f"{name}_count"):
                raise ValidationError("assurance history series transition counters are not conserved")
        expected_counts = {item.value: getattr(self, f"{item.value}_history_count") for item in HistorySeriesState if item != HistorySeriesState.MIXED and item != HistorySeriesState.EMPTY}
        expected_counts[HistorySeriesState.EMPTY.value] = self.empty_history_count
        expected_counts[HistorySeriesState.MIXED.value] = self.mixed_history_count
        if state_counts != expected_counts:
            raise ValidationError("assurance history series state counters are not conserved")
        for value, field in ((self.ready_history_count, "ready history count"), (self.held_history_count, "held history count"), (self.blocked_history_count, "blocked history count"), (self.empty_history_count, "empty history count"), (self.mixed_history_count, "mixed history count"), (self.current_ready_count, "current ready count"), (self.current_held_count, "current held count"), (self.current_blocked_count, "current blocked count"), (self.current_accepted_count, "current accepted count"), (self.current_release_ready_count, "current release-ready count"), (self.initial_count, "initial count"), (self.stable_count, "stable count"), (self.improved_count, "improved count"), (self.regressed_count, "regressed count"), (self.changed_count, "changed count"), (self.accepted_observation_count, "accepted observation count"), (self.release_ready_observation_count, "release-ready observation count")):
            _count(value, f"assurance history series {field}", max(MAX_HISTORIES, history_model.MAX_ENTRIES * MAX_HISTORIES))
        if sum(state_counts.values()) != self.history_count:
            raise ValidationError("assurance history series state counts exceed histories")
        _state(self.current_state)
        non_empty_states = {entry.current_state for entry in self.entries if entry.current_state != HistorySeriesState.EMPTY.value}
        expected_state = HistorySeriesState.EMPTY.value if not self.entries else next(iter(non_empty_states)) if len(non_empty_states) == 1 and not any(entry.current_state == HistorySeriesState.MIXED.value for entry in self.entries) else HistorySeriesState.MIXED.value
        if self.current_state != expected_state:
            raise ValidationError("assurance history series current state is invalid")
        if self.current_ready_count != sum(entry.current_state == HistorySeriesState.READY.value for entry in self.entries) or self.current_held_count != sum(entry.current_state == HistorySeriesState.HELD.value for entry in self.entries) or self.current_blocked_count != sum(entry.current_state == HistorySeriesState.BLOCKED.value for entry in self.entries) or self.current_accepted_count != sum(entry.current_accepted for entry in self.entries) or self.current_release_ready_count != sum(entry.current_release_ready for entry in self.entries):
            raise ValidationError("assurance history series current projection is invalid")
        _address(self.content_address, "assurance history series address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series(self) != self.content_address:
            raise ValidationError("assurance history series address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("assurance history series crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"series_id": self.series_id, "history_count": self.history_count, "observation_count": self.observation_count, "current_state": self.current_state, "ready_history_count": self.ready_history_count, "held_history_count": self.held_history_count, "blocked_history_count": self.blocked_history_count, "empty_history_count": self.empty_history_count, "mixed_history_count": self.mixed_history_count, "current_ready_count": self.current_ready_count, "current_held_count": self.current_held_count, "current_blocked_count": self.current_blocked_count, "current_accepted_count": self.current_accepted_count, "current_release_ready_count": self.current_release_ready_count, "initial_count": self.initial_count, "stable_count": self.stable_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "changed_count": self.changed_count, "accepted_observation_count": self.accepted_observation_count, "release_ready_observation_count": self.release_ready_observation_count, "content_address": self.content_address}

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body = {"series_id": self.series_id, "version": self.version, "boundary": self.boundary, "history_count": self.history_count, "observation_count": self.observation_count, "current_state": self.current_state, "ready_history_count": self.ready_history_count, "held_history_count": self.held_history_count, "blocked_history_count": self.blocked_history_count, "empty_history_count": self.empty_history_count, "mixed_history_count": self.mixed_history_count, "current_ready_count": self.current_ready_count, "current_held_count": self.current_held_count, "current_blocked_count": self.current_blocked_count, "current_accepted_count": self.current_accepted_count, "current_release_ready_count": self.current_release_ready_count, "initial_count": self.initial_count, "stable_count": self.stable_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "changed_count": self.changed_count, "accepted_observation_count": self.accepted_observation_count, "release_ready_observation_count": self.release_ready_observation_count, "content_address": self.content_address}
        if include_entries:
            body["entries"] = [entry.to_dict() for entry in self.entries]
        return body


def address_decision_assurance_history_series(value: DecisionAssuranceHistorySeries) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SERIES_PREFIX)


def _build_series_body(series_id: str, entries: Sequence[DecisionAssuranceHistorySeriesEntry]) -> dict[str, Any]:
    state_counts = {item.value: 0 for item in HistorySeriesState}
    for entry in entries:
        state_counts[entry.current_state] += 1
    non_empty_states = {entry.current_state for entry in entries if entry.current_state != HistorySeriesState.EMPTY.value}
    current_state = HistorySeriesState.EMPTY.value if not entries else next(iter(non_empty_states)) if len(non_empty_states) == 1 and not any(entry.current_state == HistorySeriesState.MIXED.value for entry in entries) else HistorySeriesState.MIXED.value
    def total(name: str) -> int:
        return sum(getattr(entry, f"{name}_count") for entry in entries)
    body = {"series_id": series_id, "version": VERSION, "boundary": BOUNDARY, "history_count": len(entries), "observation_count": sum(entry.entry_count for entry in entries), "current_state": current_state, "ready_history_count": state_counts["ready"], "held_history_count": state_counts["held"], "blocked_history_count": state_counts["blocked"], "empty_history_count": state_counts["empty"], "mixed_history_count": state_counts["mixed"], "current_ready_count": sum(entry.current_state == "ready" for entry in entries), "current_held_count": sum(entry.current_state == "held" for entry in entries), "current_blocked_count": sum(entry.current_state == "blocked" for entry in entries), "current_accepted_count": sum(entry.current_accepted for entry in entries), "current_release_ready_count": sum(entry.current_release_ready for entry in entries), "initial_count": total("initial"), "stable_count": total("stable"), "improved_count": total("improved"), "regressed_count": total("regressed"), "changed_count": total("changed"), "accepted_observation_count": sum(entry.accepted_count for entry in entries), "release_ready_observation_count": sum(entry.release_ready_count for entry in entries), "entries": tuple(entries), "content_address": "pending:series"}
    return body


def _series_from_histories(histories: Sequence[DecisionAssuranceHistory], series_id: str) -> DecisionAssuranceHistorySeries:
    if not isinstance(series_id, str) or not series_id.strip():
        raise ValidationError("assurance history series ID must be non-empty")
    verified = []
    for value in histories:
        verified.append(history_model.verify_decision_assurance_history(value))
    if len(verified) > MAX_HISTORIES:
        raise ValidationError("assurance history series exceeds maximum histories")
    if len({value.history_id for value in verified}) != len(verified):
        raise ValidationError("assurance history series IDs must be unique")
    entries = tuple(_entry_from_history(value, ordinal) for ordinal, value in enumerate(sorted(verified, key=lambda item: item.history_id)))
    body = _build_series_body(series_id, entries)
    provisional = DecisionAssuranceHistorySeries(**body)
    body["content_address"] = address_decision_assurance_history_series(provisional)
    result = DecisionAssuranceHistorySeries(**body)
    result._source_histories = tuple(verified)
    return result


def build_decision_assurance_history_series(histories: Sequence[DecisionAssuranceHistory] = (), *, series_id: str = DEFAULT_SERIES_ID) -> DecisionAssuranceHistorySeries:
    if not isinstance(histories, (list, tuple)):
        raise ValidationError("assurance history series histories must be an array")
    return _series_from_histories(histories, series_id)


def append_decision_assurance_history_series(series: DecisionAssuranceHistorySeries, history: DecisionAssuranceHistory, *, expected_address: str | None = None) -> DecisionAssuranceHistorySeries:
    verify_decision_assurance_history_series(series)
    history_model.verify_decision_assurance_history(history)
    if expected_address is not None and expected_address != series.content_address:
        raise ValidationError("assurance history series expected address does not match")
    if history.history_id in {entry.history_id for entry in series.entries}:
        raise ValidationError("assurance history ID already exists in series")
    source_histories = getattr(series, "_source_histories", None)
    if source_histories is None:
        raise ValidationError("series append requires source histories; use build_decision_assurance_history_series")
    return _series_from_histories(tuple(source_histories) + (history,), series.series_id)


def verify_decision_assurance_history_series(value: DecisionAssuranceHistorySeries) -> DecisionAssuranceHistorySeries:
    if not isinstance(value, DecisionAssuranceHistorySeries):
        raise ValidationError("assurance history series verification requires a typed series")
    value._validate()
    if address_decision_assurance_history_series(value) != value.content_address:
        raise ValidationError("assurance history series address mismatch")
    return value


def decision_assurance_history_series_entry_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesEntry:
    body = dict(_mapping(value, "series history entry"))
    _strict(body, {"ordinal", "history_id", "history_address", "head_address", "entry_count", "initial_snapshot_id", "current_snapshot_id", "current_assurance_state", "current_gate_state", "current_state", "current_accepted", "current_release_ready", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "accepted_count", "release_ready_count", "content_address"}, "series history entry")
    entry = DecisionAssuranceHistorySeriesEntry(**body)
    if address_decision_assurance_history_series_entry(entry) != entry.content_address:
        raise ValidationError("series history entry address mismatch")
    return entry


def decision_assurance_history_series_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeries:
    body = dict(_mapping(value, "assurance history series"))
    _strict(body, {"series_id", "version", "boundary", "history_count", "observation_count", "current_state", "ready_history_count", "held_history_count", "blocked_history_count", "empty_history_count", "mixed_history_count", "current_ready_count", "current_held_count", "current_blocked_count", "current_accepted_count", "current_release_ready_count", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "accepted_observation_count", "release_ready_observation_count", "entries", "content_address"}, "assurance history series")
    entries = tuple(decision_assurance_history_series_entry_from_mapping(item) for item in _mapping_sequence(body.pop("entries"), "series history entries"))
    return verify_decision_assurance_history_series(DecisionAssuranceHistorySeries(**body, entries=entries))


class DecisionAssuranceHistorySeriesDiffItem:
    """One history-level result in a series comparison."""

    def __init__(self, ordinal: int, history_id: str, action: str, direction: str, baseline_entry_address: str | None, candidate_entry_address: str | None, baseline_state: str | None, candidate_state: str | None, baseline_gate_state: str | None, candidate_gate_state: str | None, baseline_entry_count: int, candidate_entry_count: int, content_address: str) -> None:
        self.ordinal = ordinal
        self.history_id = history_id
        self.action = action
        self.direction = direction
        self.baseline_entry_address = baseline_entry_address
        self.candidate_entry_address = candidate_entry_address
        self.baseline_state = baseline_state
        self.candidate_state = candidate_state
        self.baseline_gate_state = baseline_gate_state
        self.candidate_gate_state = candidate_gate_state
        self.baseline_entry_count = baseline_entry_count
        self.candidate_entry_count = candidate_entry_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "series diff ordinal", MAX_HISTORIES * 2)
        _text(self.history_id, "series diff history ID", 256)
        if self.action not in {item.value for item in HistorySeriesChangeAction}:
            raise ValidationError("series diff action is invalid")
        if self.direction not in {item.value for item in HistorySeriesChangeDirection}:
            raise ValidationError("series diff direction is invalid")
        _optional_address(self.baseline_entry_address, "baseline series entry address")
        _optional_address(self.candidate_entry_address, "candidate series entry address")
        if self.action == HistorySeriesChangeAction.ADDED.value and self.baseline_entry_address is not None:
            raise ValidationError("added diff cannot have a baseline entry")
        if self.action == HistorySeriesChangeAction.REMOVED.value and self.candidate_entry_address is not None:
            raise ValidationError("removed diff cannot have a candidate entry")
        _history_state(self.baseline_state) if self.baseline_state is not None else None
        _history_state(self.candidate_state) if self.candidate_state is not None else None
        _optional_gate_state(self.baseline_gate_state)
        _optional_gate_state(self.candidate_gate_state)
        _count(self.baseline_entry_count, "baseline series observation count", history_model.MAX_ENTRIES)
        _count(self.candidate_entry_count, "candidate series observation count", history_model.MAX_ENTRIES)
        _address(self.content_address, "series diff item address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_diff_item(self) != self.content_address:
            raise ValidationError("series diff item address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "history_id": self.history_id, "action": self.action, "direction": self.direction, "baseline_entry_address": self.baseline_entry_address, "candidate_entry_address": self.candidate_entry_address, "baseline_state": self.baseline_state, "candidate_state": self.candidate_state, "baseline_gate_state": self.baseline_gate_state, "candidate_gate_state": self.candidate_gate_state, "baseline_entry_count": self.baseline_entry_count, "candidate_entry_count": self.candidate_entry_count, "content_address": self.content_address}


def address_decision_assurance_history_series_diff_item(value: DecisionAssuranceHistorySeriesDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


class DecisionAssuranceHistorySeriesDiff:
    """Addressed comparison between two independently verified series."""

    def __init__(self, baseline_address: str, candidate_address: str, baseline_series_id: str, candidate_series_id: str, baseline_history_count: int, candidate_history_count: int, added_count: int, removed_count: int, unchanged_count: int, changed_count: int, improved_count: int, regressed_count: int, state_changed_count: int, items: Sequence[DecisionAssuranceHistorySeriesDiffItem], content_address: str) -> None:
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.baseline_series_id = baseline_series_id
        self.candidate_series_id = candidate_series_id
        self.baseline_history_count = baseline_history_count
        self.candidate_history_count = candidate_history_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.state_changed_count = state_changed_count
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.baseline_address, "baseline series address")
        _address(self.candidate_address, "candidate series address")
        _text(self.baseline_series_id, "baseline series ID", 256)
        _text(self.candidate_series_id, "candidate series ID", 256)
        _count(self.baseline_history_count, "baseline history count", MAX_HISTORIES)
        _count(self.candidate_history_count, "candidate history count", MAX_HISTORIES)
        if len(self.items) != len({item.history_id for item in self.items}):
            raise ValidationError("series diff history IDs are not unique")
        if tuple(item.ordinal for item in self.items) != tuple(range(len(self.items))):
            raise ValidationError("series diff ordinals are not contiguous")
        for item in self.items:
            if not isinstance(item, DecisionAssuranceHistorySeriesDiffItem):
                raise ValidationError("series diff contains an invalid item")
            if address_decision_assurance_history_series_diff_item(item) != item.content_address:
                raise ValidationError("series diff item address mismatch")
        counts = {item.value: sum(diff.action == item.value for diff in self.items) for item in HistorySeriesChangeAction}
        if (self.added_count, self.removed_count, self.unchanged_count, self.changed_count) != tuple(counts[item.value] for item in HistorySeriesChangeAction):
            raise ValidationError("series diff action counts are not conserved")
        if self.added_count + self.unchanged_count + self.changed_count != self.candidate_history_count or self.removed_count + self.unchanged_count + self.changed_count != self.baseline_history_count:
            raise ValidationError("series diff history counts are not conserved")
        _count(self.improved_count, "series diff improved count", MAX_HISTORIES * 2)
        _count(self.regressed_count, "series diff regressed count", MAX_HISTORIES * 2)
        _count(self.state_changed_count, "series diff state changed count", MAX_HISTORIES * 2)
        if self.improved_count + self.regressed_count > self.changed_count or self.state_changed_count > self.changed_count:
            raise ValidationError("series diff directional counts are invalid")
        _address(self.content_address, "series diff address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_diff(self) != self.content_address:
            raise ValidationError("series diff address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "baseline_series_id": self.baseline_series_id, "candidate_series_id": self.candidate_series_id, "baseline_history_count": self.baseline_history_count, "candidate_history_count": self.candidate_history_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "state_changed_count": self.state_changed_count, "content_address": self.content_address}

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def address_decision_assurance_history_series_diff(value: DecisionAssuranceHistorySeriesDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _diff_direction(baseline: DecisionAssuranceHistorySeriesEntry | None, candidate: DecisionAssuranceHistorySeriesEntry | None) -> str:
    if baseline is None or candidate is None:
        return HistorySeriesChangeDirection.CHANGED.value
    baseline_score = _score(baseline.current_gate_state)
    candidate_score = _score(candidate.current_gate_state)
    if candidate_score > baseline_score:
        return HistorySeriesChangeDirection.IMPROVED.value
    if candidate_score < baseline_score:
        return HistorySeriesChangeDirection.REGRESSED.value
    return HistorySeriesChangeDirection.CHANGED.value


def diff_decision_assurance_history_series(baseline: DecisionAssuranceHistorySeries, candidate: DecisionAssuranceHistorySeries) -> DecisionAssuranceHistorySeriesDiff:
    verify_decision_assurance_history_series(baseline)
    verify_decision_assurance_history_series(candidate)
    left = {entry.history_id: entry for entry in baseline.entries}
    right = {entry.history_id: entry for entry in candidate.entries}
    items: list[DecisionAssuranceHistorySeriesDiffItem] = []
    for ordinal, history_id in enumerate(sorted(set(left) | set(right))):
        old = left.get(history_id)
        new = right.get(history_id)
        if old is None:
            action = HistorySeriesChangeAction.ADDED.value
        elif new is None:
            action = HistorySeriesChangeAction.REMOVED.value
        elif old.content_address == new.content_address:
            action = HistorySeriesChangeAction.UNCHANGED.value
        else:
            action = HistorySeriesChangeAction.CHANGED.value
        body = {"ordinal": ordinal, "history_id": history_id, "action": action, "direction": _diff_direction(old, new), "baseline_entry_address": old.content_address if old else None, "candidate_entry_address": new.content_address if new else None, "baseline_state": old.current_state if old else None, "candidate_state": new.current_state if new else None, "baseline_gate_state": old.current_gate_state if old else None, "candidate_gate_state": new.current_gate_state if new else None, "baseline_entry_count": old.entry_count if old else 0, "candidate_entry_count": new.entry_count if new else 0, "content_address": "pending:series-diff-item"}
        provisional = DecisionAssuranceHistorySeriesDiffItem(**body)
        body["content_address"] = address_decision_assurance_history_series_diff_item(provisional)
        items.append(DecisionAssuranceHistorySeriesDiffItem(**body))
    body = {"baseline_address": baseline.content_address, "candidate_address": candidate.content_address, "baseline_series_id": baseline.series_id, "candidate_series_id": candidate.series_id, "baseline_history_count": baseline.history_count, "candidate_history_count": candidate.history_count, "added_count": sum(item.action == "added" for item in items), "removed_count": sum(item.action == "removed" for item in items), "unchanged_count": sum(item.action == "unchanged" for item in items), "changed_count": sum(item.action == "changed" for item in items), "improved_count": sum(item.direction == "improved" for item in items), "regressed_count": sum(item.direction == "regressed" for item in items), "state_changed_count": sum(item.baseline_state != item.candidate_state for item in items if item.action == "changed"), "items": tuple(items), "content_address": "pending:series-diff"}
    provisional = DecisionAssuranceHistorySeriesDiff(**body)
    body["content_address"] = address_decision_assurance_history_series_diff(provisional)
    return DecisionAssuranceHistorySeriesDiff(**body)


def verify_decision_assurance_history_series_diff(value: DecisionAssuranceHistorySeriesDiff) -> DecisionAssuranceHistorySeriesDiff:
    if not isinstance(value, DecisionAssuranceHistorySeriesDiff):
        raise ValidationError("assurance history series diff verification requires a typed diff")
    value._validate()
    if address_decision_assurance_history_series_diff(value) != value.content_address:
        raise ValidationError("assurance history series diff address mismatch")
    return value


def decision_assurance_history_series_diff_item_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesDiffItem:
    body = dict(_mapping(value, "series diff item"))
    _strict(body, {"ordinal", "history_id", "action", "direction", "baseline_entry_address", "candidate_entry_address", "baseline_state", "candidate_state", "baseline_gate_state", "candidate_gate_state", "baseline_entry_count", "candidate_entry_count", "content_address"}, "series diff item")
    item = DecisionAssuranceHistorySeriesDiffItem(**body)
    if address_decision_assurance_history_series_diff_item(item) != item.content_address:
        raise ValidationError("series diff item address mismatch")
    return item


def decision_assurance_history_series_diff_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesDiff:
    body = dict(_mapping(value, "series diff"))
    _strict(body, {"baseline_address", "candidate_address", "baseline_series_id", "candidate_series_id", "baseline_history_count", "candidate_history_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "state_changed_count", "items", "content_address"}, "series diff")
    items = tuple(decision_assurance_history_series_diff_item_from_mapping(item) for item in _mapping_sequence(body.pop("items"), "series diff items"))
    return verify_decision_assurance_history_series_diff(DecisionAssuranceHistorySeriesDiff(**body, items=items))


class DecisionAssuranceHistorySeriesReplayCheck:
    """One independently evaluated series invariant."""

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
        _count(self.ordinal, "series replay check ordinal", 32)
        _text(self.check_id, "series replay check ID", 256)
        _text(self.kind, "series replay check kind", 128)
        _bool(self.passed, "series replay check passed")
        _bool(self.required, "series replay check required")
        _text(self.detail, "series replay check detail", 1024)
        _address(self.evidence_address, "series replay evidence address")
        _address(self.content_address, "series replay check address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_replay_check(self) != self.content_address:
            raise ValidationError("series replay check address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series replay check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "kind": self.kind, "passed": self.passed, "required": self.required, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}


def address_decision_assurance_history_series_replay_check(value: DecisionAssuranceHistorySeriesReplayCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REPLAY_CHECK_PREFIX)


class DecisionAssuranceHistorySeriesReplay:
    """Independent replay result for a series aggregate."""

    def __init__(self, series_address: str, series_id: str, history_count: int, observation_count: int, check_count: int, passed_count: int, failure_count: int, state: str, accepted: bool, release_ready: bool, checks: Sequence[DecisionAssuranceHistorySeriesReplayCheck], content_address: str) -> None:
        self.series_address = series_address
        self.series_id = series_id
        self.history_count = history_count
        self.observation_count = observation_count
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
        _address(self.series_address, "series replay source address")
        _text(self.series_id, "series replay ID", 256)
        _count(self.history_count, "series replay history count", MAX_HISTORIES)
        _count(self.observation_count, "series replay observation count", history_model.MAX_ENTRIES * MAX_HISTORIES)
        _count(self.check_count, "series replay check count", 32)
        _count(self.passed_count, "series replay passed count", 32)
        _count(self.failure_count, "series replay failure count", 32)
        if self.check_count != len(self.checks) or self.passed_count + self.failure_count != self.check_count:
            raise ValidationError("series replay check counts are not conserved")
        if sum(check.passed for check in self.checks) != self.passed_count:
            raise ValidationError("series replay passed count is not conserved")
        if self.state not in {item.value for item in HistorySeriesReplayState}:
            raise ValidationError("series replay state is invalid")
        _bool(self.accepted, "series replay accepted")
        _bool(self.release_ready, "series replay release readiness")
        if self.accepted != (self.failure_count == 0) or self.release_ready != (self.accepted and self.history_count > 0):
            raise ValidationError("series replay readiness is invalid")
        _address(self.content_address, "series replay address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_replay(self) != self.content_address:
            raise ValidationError("series replay address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series replay crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"series_address": self.series_address, "series_id": self.series_id, "history_count": self.history_count, "observation_count": self.observation_count, "check_count": self.check_count, "passed_count": self.passed_count, "failure_count": self.failure_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"checks": [check.to_dict() for check in self.checks]}


def address_decision_assurance_history_series_replay(value: DecisionAssuranceHistorySeriesReplay) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REPLAY_PREFIX)


def _replay_check(ordinal: int, series: DecisionAssuranceHistorySeries, kind: str, passed: bool, detail: str) -> DecisionAssuranceHistorySeriesReplayCheck:
    body = {"ordinal": ordinal, "check_id": f"{series.series_id}:replay:{ordinal}", "kind": kind, "passed": passed, "required": True, "detail": detail, "evidence_address": series.content_address, "content_address": "pending:series-replay-check"}
    provisional = DecisionAssuranceHistorySeriesReplayCheck(**body)
    body["content_address"] = address_decision_assurance_history_series_replay_check(provisional)
    return DecisionAssuranceHistorySeriesReplayCheck(**body)


def replay_decision_assurance_history_series(series: DecisionAssuranceHistorySeries) -> DecisionAssuranceHistorySeriesReplay:
    verify_decision_assurance_history_series(series)
    checks = (
        _replay_check(0, series, "entry-addresses", all(address_decision_assurance_history_series_entry(entry) == entry.content_address for entry in series.entries), "every series entry address recomputes"),
        _replay_check(1, series, "ordinal-order", tuple(entry.ordinal for entry in series.entries) == tuple(range(series.history_count)) and tuple(entry.history_id for entry in series.entries) == tuple(sorted(entry.history_id for entry in series.entries)), "series entries are contiguous and sorted"),
        _replay_check(2, series, "history-count", series.history_count == len(series.entries), "history count equals retained entries"),
        _replay_check(3, series, "observation-conservation", series.observation_count == sum(entry.entry_count for entry in series.entries), "observation count equals the retained history totals"),
        _replay_check(4, series, "state-projection", series.current_state == ("empty" if not series.entries else next(iter({entry.current_state for entry in series.entries if entry.current_state != "empty"})) if len({entry.current_state for entry in series.entries if entry.current_state != "empty"}) == 1 and not any(entry.current_state == "mixed" for entry in series.entries) else "mixed"), "current series state replays from history states"),
        _replay_check(5, series, "transition-conservation", series.initial_count + series.stable_count + series.improved_count + series.regressed_count + series.changed_count == series.observation_count, "transition totals equal observations"),
        _replay_check(6, series, "public-boundary", _public(series.to_dict()), "series contains only public fields"),
        _replay_check(7, series, "content-address", address_decision_assurance_history_series(series) == series.content_address, "series content address recomputes"),
    )
    passed = sum(check.passed for check in checks)
    body = {"series_address": series.content_address, "series_id": series.series_id, "history_count": series.history_count, "observation_count": series.observation_count, "check_count": len(checks), "passed_count": passed, "failure_count": len(checks) - passed, "state": HistorySeriesReplayState.PASSED.value if passed == len(checks) else HistorySeriesReplayState.BLOCKED.value, "accepted": passed == len(checks), "release_ready": passed == len(checks) and series.history_count > 0, "checks": checks, "content_address": "pending:series-replay"}
    provisional = DecisionAssuranceHistorySeriesReplay(**body)
    body["content_address"] = address_decision_assurance_history_series_replay(provisional)
    return DecisionAssuranceHistorySeriesReplay(**body)


def verify_decision_assurance_history_series_replay(value: DecisionAssuranceHistorySeriesReplay) -> DecisionAssuranceHistorySeriesReplay:
    if not isinstance(value, DecisionAssuranceHistorySeriesReplay):
        raise ValidationError("series replay verification requires a typed replay")
    value._validate()
    for check in value.checks:
        if address_decision_assurance_history_series_replay_check(check) != check.content_address:
            raise ValidationError("series replay check address mismatch")
    if address_decision_assurance_history_series_replay(value) != value.content_address:
        raise ValidationError("series replay address mismatch")
    return value


def decision_assurance_history_series_replay_check_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReplayCheck:
    body = dict(_mapping(value, "series replay check"))
    _strict(body, {"ordinal", "check_id", "kind", "passed", "required", "detail", "evidence_address", "content_address"}, "series replay check")
    return DecisionAssuranceHistorySeriesReplayCheck(**body)


def decision_assurance_history_series_replay_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReplay:
    body = dict(_mapping(value, "series replay"))
    _strict(body, {"series_address", "series_id", "history_count", "observation_count", "check_count", "passed_count", "failure_count", "state", "accepted", "release_ready", "checks", "content_address"}, "series replay")
    checks = tuple(decision_assurance_history_series_replay_check_from_mapping(item) for item in _mapping_sequence(body.pop("checks"), "series replay checks"))
    return verify_decision_assurance_history_series_replay(DecisionAssuranceHistorySeriesReplay(**body, checks=checks))


class AssuranceHistorySeriesQuery:
    """Bounded query over series history summaries."""

    def __init__(self, resource: str = "summary", *, state: str | None = None, gate_state: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "assurance history series query resource", 64)
        valid = {"summary", "histories", "ready", "held", "blocked", "empty", "mixed", "accepted", "release-ready", "states"}
        if self.resource not in valid:
            raise ValidationError("assurance history series query resource is invalid")
        if state is not None:
            _state(state, "assurance history series query state")
        if gate_state is not None:
            _gate_state(gate_state, "assurance history series query gate state")
        self.state = state
        self.gate_state = gate_state
        self.text = _text(text, "assurance history series query text", 256).casefold() if text is not None else None
        self.offset = _count(offset, "assurance history series query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "assurance history series query limit", MAX_QUERY_ITEMS, positive=True)
        if self.offset + self.limit > MAX_QUERY_ITEMS:
            raise ValidationError("assurance history series query window is too large")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "state": self.state, "gate_state": self.gate_state, "text": self.text, "offset": self.offset, "limit": self.limit}


class AssuranceHistorySeriesQueryResult:
    def __init__(self, query: AssuranceHistorySeriesQuery, total_count: int, items: Sequence[Mapping[str, Any]], source_address: str) -> None:
        self.query = query
        self.total_count = _count(total_count, "assurance history series query total count", MAX_QUERY_ITEMS)
        self.items = tuple(dict(item) for item in items)
        self.returned_count = _count(len(self.items), "assurance history series query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count:
            raise ValidationError("assurance history series query returned count exceeds total")
        self.source_address = _address(source_address, "assurance history series query source address")
        self.content_address = "pending:series-query"
        self.content_address = content_hash(self.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-result")
        if not _public(self.to_dict()):
            raise ValidationError("assurance history series query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "source_address": self.source_address, "content_address": self.content_address}


def query_decision_assurance_history_series(series: DecisionAssuranceHistorySeries, query: AssuranceHistorySeriesQuery | None = None, **kwargs: Any) -> AssuranceHistorySeriesQueryResult:
    verify_decision_assurance_history_series(series)
    selected = query if query is not None else AssuranceHistorySeriesQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    records: tuple[Mapping[str, Any], ...] = (series.summary(),) if selected.resource == "summary" else tuple(entry.to_dict() for entry in series.entries)
    if selected.resource in {item.value for item in HistorySeriesState}:
        records = tuple(item for item in records if item.get("current_state") == selected.resource)
    elif selected.resource == "accepted":
        records = tuple(item for item in records if item.get("current_accepted"))
    elif selected.resource == "release-ready":
        records = tuple(item for item in records if item.get("current_release_ready"))
    elif selected.resource == "states":
        records = tuple({"state": state, "count": sum(entry.current_state == state for entry in series.entries)} for state in sorted({entry.current_state for entry in series.entries}))
    matched = tuple(item for item in records if (selected.state is None or item.get("current_state") == selected.state) and (selected.gate_state is None or item.get("current_gate_state") == selected.gate_state) and (selected.text is None or selected.text in canonical_json(item).casefold()))
    return AssuranceHistorySeriesQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], series.content_address)


def decision_assurance_history_series_json(value: DecisionAssuranceHistorySeries) -> str:
    verify_decision_assurance_history_series(value)
    return canonical_json(value.to_dict())


def decision_assurance_history_series_csv(value: DecisionAssuranceHistorySeries) -> str:
    verify_decision_assurance_history_series(value)
    return _csv_text([entry.to_dict() for entry in value.entries], ("ordinal", "history_id", "history_address", "head_address", "entry_count", "current_state", "current_gate_state", "current_accepted", "current_release_ready", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "accepted_count", "release_ready_count", "content_address"))


def decision_assurance_history_series_diff_json(value: DecisionAssuranceHistorySeriesDiff) -> str:
    verify_decision_assurance_history_series_diff(value)
    return canonical_json(value.to_dict())


def decision_assurance_history_series_diff_csv(value: DecisionAssuranceHistorySeriesDiff) -> str:
    verify_decision_assurance_history_series_diff(value)
    return _csv_text([item.to_dict() for item in value.items], ("ordinal", "history_id", "action", "direction", "baseline_entry_address", "candidate_entry_address", "baseline_state", "candidate_state", "baseline_gate_state", "candidate_gate_state", "baseline_entry_count", "candidate_entry_count", "content_address"))


def decision_assurance_history_series_replay_json(value: DecisionAssuranceHistorySeriesReplay) -> str:
    verify_decision_assurance_history_series_replay(value)
    return canonical_json(value.to_dict())


def decision_assurance_history_series_replay_csv(value: DecisionAssuranceHistorySeriesReplay) -> str:
    verify_decision_assurance_history_series_replay(value)
    return _csv_text([check.to_dict() for check in value.checks], ("ordinal", "check_id", "kind", "passed", "required", "detail", "evidence_address", "content_address"))


def decision_assurance_history_series_query_json(value: AssuranceHistorySeriesQueryResult) -> str:
    return canonical_json(value.to_dict())


def decision_assurance_history_series_query_csv(value: AssuranceHistorySeriesQueryResult) -> str:
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
        lines.extend(("| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"))
        lines.extend("| " + " | ".join(canonical_json(row.get(field, "")).replace("|", "\\|") for field in fields) + " |" for row in rows)
    else:
        lines.extend(("", "No records."))
    return "\n".join(lines) + "\n"


def render_decision_assurance_history_series_markdown(value: DecisionAssuranceHistorySeries) -> str:
    verify_decision_assurance_history_series(value)
    return _markdown("Federation Review Decision Assurance History Series", value.summary(), [entry.to_dict() for entry in value.entries])


def render_decision_assurance_history_series_diff_markdown(value: DecisionAssuranceHistorySeriesDiff) -> str:
    verify_decision_assurance_history_series_diff(value)
    return _markdown("Federation Review Decision Assurance History Series Diff", value.summary(), [item.to_dict() for item in value.items])


def render_decision_assurance_history_series_replay_markdown(value: DecisionAssuranceHistorySeriesReplay) -> str:
    verify_decision_assurance_history_series_replay(value)
    return _markdown("Federation Review Decision Assurance History Series Replay", value.summary(), [check.to_dict() for check in value.checks])


def render_decision_assurance_history_series_query_markdown(value: AssuranceHistorySeriesQueryResult) -> str:
    return _markdown("Federation Review Decision Assurance History Series Query", {"resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def decision_assurance_history_series_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Series", "type": "object", "additionalProperties": False, "properties": {"series_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "history_count": {"type": "integer", "minimum": 0, "maximum": MAX_HISTORIES}, "observation_count": {"type": "integer", "minimum": 0}, "current_state": {"enum": [item.value for item in HistorySeriesState]}, "entries": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["series_id", "version", "boundary", "history_count", "observation_count", "current_state", "content_address"]}


def decision_assurance_history_series_entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Series Entry", "type": "object", "additionalProperties": False, "properties": {"ordinal": {"type": "integer", "minimum": 0}, "history_id": {"type": "string"}, "current_state": {"enum": [item.value for item in HistorySeriesState]}, "current_gate_state": {"type": ["string", "null"]}, "content_address": {"type": "string"}}, "required": ["ordinal", "history_id", "current_state", "content_address"]}


def decision_assurance_history_series_diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Series Diff", "type": "object", "additionalProperties": False, "properties": {"baseline_address": {"type": "string"}, "candidate_address": {"type": "string"}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "items": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["baseline_address", "candidate_address", "added_count", "removed_count", "unchanged_count", "changed_count", "content_address"]}


def decision_assurance_history_series_diff_item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Series Diff Item", "type": "object", "additionalProperties": False, "properties": {"history_id": {"type": "string"}, "action": {"enum": [item.value for item in HistorySeriesChangeAction]}, "direction": {"enum": [item.value for item in HistorySeriesChangeDirection]}, "content_address": {"type": "string"}}, "required": ["history_id", "action", "direction", "content_address"]}


def decision_assurance_history_series_replay_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Series Replay", "type": "object", "additionalProperties": False, "properties": {"series_address": {"type": "string"}, "history_count": {"type": "integer", "minimum": 0}, "observation_count": {"type": "integer", "minimum": 0}, "check_count": {"type": "integer", "minimum": 0}, "state": {"enum": [item.value for item in HistorySeriesReplayState]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "content_address": {"type": "string"}}, "required": ["series_address", "history_count", "observation_count", "check_count", "state", "accepted", "release_ready", "content_address"]}


def decision_assurance_history_series_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Series Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": ["summary", "histories", "ready", "held", "blocked", "empty", "mixed", "accepted", "release-ready", "states"]}, "state": {"type": ["string", "null"]}, "gate_state": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}, "required": ["resource", "offset", "limit"]}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "series": {"maximum_histories": MAX_HISTORIES, "states": [item.value for item in HistorySeriesState]}, "diff": {"actions": [item.value for item in HistorySeriesChangeAction], "directions": [item.value for item in HistorySeriesChangeDirection]}, "replay": {"checks": 8, "states": [item.value for item in HistorySeriesReplayState]}, "persistence": {"files": list(FILES), "atomic_write": True, "canonical_json": True, "exact_file_set": True}, "queries": {"resources": ["summary", "histories", "ready", "held", "blocked", "empty", "mixed", "accepted", "release-ready", "states"], "pagination": True, "filters": ["state", "gate_state", "text"]}}


def _manifest_body(value: DecisionAssuranceHistorySeries, series_raw: bytes, entries_raw: bytes) -> dict[str, Any]:
    artifacts = [{"name": SERIES_NAME, "bytes": len(series_raw), "byte_address": hash_bytes(series_raw), "file_address": content_hash({"name": SERIES_NAME, "byte_address": hash_bytes(series_raw)}, prefix=SERIES_PREFIX + "-file")}, {"name": ENTRIES_NAME, "bytes": len(entries_raw), "byte_address": hash_bytes(entries_raw), "file_address": content_hash({"name": ENTRIES_NAME, "byte_address": hash_bytes(entries_raw)}, prefix=SERIES_PREFIX + "-file")}]
    return {"version": VERSION, "boundary": BOUNDARY, "series_id": value.series_id, "series_address": value.content_address, "history_count": value.history_count, "observation_count": value.observation_count, "artifact_count": 2, "files": list(FILES), "artifacts": artifacts, "manifest_address": None}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=MANIFEST_PREFIX)


def write_decision_assurance_history_series(value: DecisionAssuranceHistorySeries, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_assurance_history_series(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("decision assurance history series destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    series_raw = canonical_bytes(value.to_dict(include_entries=False))
    entries_raw = canonical_bytes({"series_id": value.series_id, "series_address": value.content_address, "history_count": value.history_count, "observation_count": value.observation_count, "entries": [entry.to_dict() for entry in value.entries]})
    manifest = _manifest_body(value, series_raw, entries_raw)
    manifest["manifest_address"] = _manifest_address(manifest)
    manifest_raw = canonical_bytes(manifest)
    temporary = Path(tempfile.mkdtemp(prefix=f".{SERIES_PREFIX}-", dir=str(destination.parent)))
    try:
        (temporary / SERIES_NAME).write_bytes(series_raw)
        (temporary / ENTRIES_NAME).write_bytes(entries_raw)
        (temporary / MANIFEST_NAME).write_bytes(manifest_raw)
        if destination.exists():
            if not destination.is_dir():
                raise ValidationError("decision assurance history series destination is not a directory")
            if any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("decision assurance history series destination already exists")
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
    artifact = next((item for item in _mapping_sequence(manifest.get("artifacts"), "series manifest artifacts") if item.get("name") == name), None)
    if artifact is None:
        raise ValidationError(f"series manifest is missing {name}")
    raw = path.read_bytes()
    byte_address = hash_bytes(raw)
    if artifact.get("bytes") != len(raw) or artifact.get("byte_address") != byte_address:
        raise ValidationError(f"series {name} bytes are not addressed")
    if artifact.get("file_address") != content_hash({"name": name, "byte_address": byte_address}, prefix=SERIES_PREFIX + "-file"):
        raise ValidationError(f"series {name} file address is invalid")


def load_decision_assurance_history_series(directory: str | Path) -> DecisionAssuranceHistorySeries:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("decision assurance history series input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(FILES):
        raise ValidationError("decision assurance history series file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "assurance history series manifest")
    _strict(manifest, {"version", "boundary", "series_id", "series_address", "history_count", "observation_count", "artifact_count", "files", "artifacts", "manifest_address"}, "assurance history series manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 2 or tuple(manifest["files"]) != FILES:
        raise ValidationError("assurance history series manifest contract is invalid")
    if manifest["manifest_address"] != _manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("assurance history series manifest address mismatch")
    _check_artifact(manifest, source / SERIES_NAME, SERIES_NAME)
    _check_artifact(manifest, source / ENTRIES_NAME, ENTRIES_NAME)
    summary = _read_json(source / SERIES_NAME, "assurance history series summary")
    entries_body = _read_json(source / ENTRIES_NAME, "assurance history series entries")
    _strict(entries_body, {"series_id", "series_address", "history_count", "observation_count", "entries"}, "assurance history series entries")
    if entries_body["series_id"] != manifest["series_id"] or entries_body["series_address"] != manifest["series_address"] or entries_body["history_count"] != manifest["history_count"] or entries_body["observation_count"] != manifest["observation_count"]:
        raise ValidationError("assurance history series entries linkage is invalid")
    summary["entries"] = entries_body["entries"]
    value = decision_assurance_history_series_from_mapping(summary)
    if value.series_id != manifest["series_id"] or value.content_address != manifest["series_address"] or value.history_count != manifest["history_count"]:
        raise ValidationError("assurance history series manifest linkage is invalid")
    return verify_decision_assurance_history_series(value)


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_SERIES_ID", "ENTRIES_NAME", "FILES", "MANIFEST_NAME", "MAX_HISTORIES", "MAX_QUERY_ITEMS", "SERIES_NAME", "SERIES_PREFIX", "AssuranceHistorySeriesQuery", "AssuranceHistorySeriesQueryResult", "DecisionAssuranceHistory", "DecisionAssuranceHistorySeries", "DecisionAssuranceHistorySeriesDiff", "DecisionAssuranceHistorySeriesDiffItem", "DecisionAssuranceHistorySeriesEntry", "DecisionAssuranceHistorySeriesReplay", "DecisionAssuranceHistorySeriesReplayCheck", "HistorySeriesChangeAction", "HistorySeriesChangeDirection", "HistorySeriesReplayState", "HistorySeriesState", "address_decision_assurance_history_series", "address_decision_assurance_history_series_diff", "address_decision_assurance_history_series_diff_item", "address_decision_assurance_history_series_entry", "address_decision_assurance_history_series_replay", "address_decision_assurance_history_series_replay_check", "append_decision_assurance_history_series", "build_decision_assurance_history_series", "capabilities", "decision_assurance_history_series_csv", "decision_assurance_history_series_diff_csv", "decision_assurance_history_series_diff_from_mapping", "decision_assurance_history_series_diff_item_from_mapping", "decision_assurance_history_series_diff_item_schema", "decision_assurance_history_series_diff_json", "decision_assurance_history_series_diff_schema", "decision_assurance_history_series_entry_from_mapping", "decision_assurance_history_series_entry_schema", "decision_assurance_history_series_from_mapping", "decision_assurance_history_series_json", "decision_assurance_history_series_query_csv", "decision_assurance_history_series_query_json", "decision_assurance_history_series_query_schema", "decision_assurance_history_series_replay_check_from_mapping", "decision_assurance_history_series_replay_from_mapping", "decision_assurance_history_series_replay_json", "decision_assurance_history_series_replay_schema", "decision_assurance_history_series_schema", "diff_decision_assurance_history_series", "load_decision_assurance_history_series", "query_decision_assurance_history_series", "render_decision_assurance_history_series_diff_markdown", "render_decision_assurance_history_series_markdown", "render_decision_assurance_history_series_query_markdown", "render_decision_assurance_history_series_replay_markdown", "replay_decision_assurance_history_series", "verify_decision_assurance_history_series", "verify_decision_assurance_history_series_diff", "verify_decision_assurance_history_series_replay", "write_decision_assurance_history_series"]
