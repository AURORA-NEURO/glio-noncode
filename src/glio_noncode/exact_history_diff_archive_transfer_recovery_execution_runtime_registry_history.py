"""Append-only history for history-diff recovery-execution runtime registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-history-v1"
BOUNDARY = registry_model.BOUNDARY + "_history"
HISTORY_PREFIX = registry_model.REGISTRY_PREFIX + "-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
ENTRIES_PREFIX = HISTORY_PREFIX + "-entries"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
SUMMARY_PREFIX = HISTORY_PREFIX + "-summary"
DEFAULT_HISTORY_ID = HISTORY_PREFIX
FILES = ("manifest.json", "history.json", "entries.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
MANIFEST_ARTIFACT_FILES = ("entries.json", "summary.json")
TRANSITIONS = ("initial", "improved", "regressed", "unchanged", "changed")
STATES = registry_model.STATES
MAX_ENTRIES = registry_model.MAX_ENTRIES
MAX_HISTORY_BYTES = 16 * 1024 * 1024
ENTRY_FIELDS = (
    "ordinal",
    "registry_id",
    "registry_address",
    "entry_count",
    "accepted_count",
    "ready_count",
    "blocked_count",
    "state",
    "accepted",
    "transition",
    "previous_registry_address",
    "content_address",
)
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("history_id", "registry_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = (
    "history_id",
    "registry_id",
    "entry_count",
    "latest_registry_address",
    "latest_entry_count",
    "latest_accepted_count",
    "latest_ready_count",
    "latest_blocked_count",
    "initial_count",
    "improved_count",
    "regressed_count",
    "unchanged_count",
    "changed_count",
    "state",
    "accepted",
    "content_address",
)
HISTORY_FIELDS = (
    "history_id",
    "registry_id",
    "version",
    "boundary",
    "entry_count",
    "latest_registry_address",
    "latest_entry_count",
    "latest_accepted_count",
    "latest_ready_count",
    "latest_blocked_count",
    "initial_count",
    "improved_count",
    "regressed_count",
    "unchanged_count",
    "changed_count",
    "state",
    "accepted",
    "manifest",
    "summary",
    "entries",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True, allow_pending: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if value and (":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


def _state(entry_count: int, ready_count: int, blocked_count: int) -> str:
    if not entry_count:
        return "empty"
    return "ready" if ready_count == entry_count and not blocked_count else "blocked"


def _quality(value: Any) -> tuple[int, int, int, int, int]:
    ranks = {"ready": 0, "empty": 1, "blocked": 2}
    return (ranks[value.state], -value.ready_count, -value.accepted_count, value.blocked_count, value.entry_count)


def _transition(current: Any, previous: Any | None) -> str:
    if previous is None:
        return "initial"
    current_quality = _quality(current)
    previous_quality = _quality(previous)
    if current_quality < previous_quality:
        return "improved"
    if current_quality > previous_quality:
        return "regressed"
    fields = ("entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted")
    return "unchanged" if all(getattr(current, field) == getattr(previous, field) for field in fields) else "changed"


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry:
    """One addressed registry snapshot in append order."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, registry_id: str, registry_address: str, entry_count: int, accepted_count: int, ready_count: int, blocked_count: int, state: str, accepted: bool, transition: str, previous_registry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history entry ordinal", MAX_ENTRIES, lower=1)
        self.registry_id = _label(registry_id, "runtime registry history entry registry ID")
        self.registry_address = _address(registry_address, "runtime registry history entry registry address", registry_model.REGISTRY_PREFIX)
        self.entry_count = _count(entry_count, "runtime registry history entry count", registry_model.MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "runtime registry history accepted count", registry_model.MAX_ENTRIES)
        self.ready_count = _count(ready_count, "runtime registry history ready count", registry_model.MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "runtime registry history blocked count", registry_model.MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("runtime registry history entry state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry history entry acceptance")
        self.transition = _label(transition, "runtime registry history transition")
        if self.transition not in TRANSITIONS:
            raise ValidationError("runtime registry history transition is unsupported")
        self.previous_registry_address = _address(previous_registry_address, "runtime registry history previous registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.content_address = _address(content_address, "runtime registry history entry address", ENTRY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count > self.entry_count or self.ready_count + self.blocked_count != self.entry_count:
            raise ValidationError("runtime registry history entry counts are inconsistent")
        if self.state != _state(self.entry_count, self.ready_count, self.blocked_count):
            raise ValidationError("runtime registry history entry state does not replay")
        if self.accepted != (not self.entry_count or self.accepted_count == self.entry_count):
            raise ValidationError("runtime registry history entry acceptance does not replay")
        if self.ordinal == 1 and (self.transition != "initial" or self.previous_registry_address):
            raise ValidationError("first runtime registry history entry must be initial")
        if self.ordinal > 1 and (self.transition == "initial" or not self.previous_registry_address):
            raise ValidationError("later runtime registry history entries require ancestry")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history entry crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("runtime registry history entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry:
        value = _mapping(value, "runtime registry history entry")
        _strict(value, set(cls.FIELDS), "runtime registry history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry):
        raise ValidationError("runtime registry history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def entry_from_registry(value: registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry, ordinal: int, transition: str, previous_registry_address: str) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry:
    if not isinstance(value, registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry):
        raise ValidationError("runtime registry history entries require typed registries")
    value = registry_model.verify_registry(value)
    body = {
        "ordinal": ordinal,
        "registry_id": value.registry_id,
        "registry_address": value.content_address,
        "entry_count": value.entry_count,
        "accepted_count": value.accepted_count,
        "ready_count": value.ready_count,
        "blocked_count": value.blocked_count,
        "state": value.state,
        "accepted": value.accepted,
        "transition": transition,
        "previous_registry_address": previous_registry_address,
        "content_address": ENTRY_PREFIX + ":pending",
    }
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry(**(body | {"content_address": address_entry(provisional)}))


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntries:
    """Ordered and addressed snapshot projection persisted beside a history."""

    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry.from_mapping(item) for item in _sequence(entries, "runtime registry history entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "runtime registry history entries address", ENTRIES_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history entries cross the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_entries(self.entries) != self.content_address:
            raise ValidationError("runtime registry history entries address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntries:
        value = _mapping(value, "runtime registry history entries")
        _strict(value, set(cls.FIELDS), "runtime registry history entries")
        return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry) for item in typed):
        raise ValidationError("runtime registry history entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest:
    """Canonical file and artifact-address manifest for a registry history."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, history_id: str, registry_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.history_id = _label(history_id, "runtime registry history manifest history ID")
        self.registry_id = _label(registry_id, "runtime registry history manifest registry ID", required=False)
        self.version = _text(version, "runtime registry history manifest version")
        self.boundary = _text(boundary, "runtime registry history manifest boundary")
        self.files = tuple(_label(item, "runtime registry history manifest file") for item in _sequence(files, "runtime registry history manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "runtime registry history manifest artifact address") for item in _sequence(artifact_addresses, "runtime registry history manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "runtime registry history manifest address", MANIFEST_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if (self.version, self.boundary) != (VERSION, BOUNDARY) or self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("runtime registry history manifest does not close the public file boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("runtime registry history manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest:
        value = _mapping(value, "runtime registry history manifest")
        _strict(value, set(cls.FIELDS), "runtime registry history manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest):
        raise ValidationError("runtime registry history manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary:
    """Conserved trend counters and latest disposition for a history."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, history_id: str, registry_id: str, entry_count: int, latest_registry_address: str, latest_entry_count: int, latest_accepted_count: int, latest_ready_count: int, latest_blocked_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "runtime registry history summary history ID")
        self.registry_id = _label(registry_id, "runtime registry history summary registry ID", required=False)
        self.entry_count = _count(entry_count, "runtime registry history summary entry count", MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "runtime registry history summary latest registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.latest_entry_count = _count(latest_entry_count, "runtime registry history summary latest entry count", registry_model.MAX_ENTRIES)
        self.latest_accepted_count = _count(latest_accepted_count, "runtime registry history summary latest accepted count", registry_model.MAX_ENTRIES)
        self.latest_ready_count = _count(latest_ready_count, "runtime registry history summary latest ready count", registry_model.MAX_ENTRIES)
        self.latest_blocked_count = _count(latest_blocked_count, "runtime registry history summary latest blocked count", registry_model.MAX_ENTRIES)
        self.initial_count = _count(initial_count, "runtime registry history summary initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "runtime registry history summary improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "runtime registry history summary regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "runtime registry history summary unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "runtime registry history summary changed count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("runtime registry history summary state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry history summary acceptance")
        self.content_address = _address(content_address, "runtime registry history summary address", SUMMARY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.latest_accepted_count > self.latest_entry_count or self.latest_ready_count + self.latest_blocked_count != self.latest_entry_count:
            raise ValidationError("runtime registry history summary latest counts are inconsistent")
        if self.latest_entry_count and self.state != _state(self.latest_entry_count, self.latest_ready_count, self.latest_blocked_count):
            raise ValidationError("runtime registry history summary state does not replay")
        if not self.entry_count and (self.latest_registry_address or self.latest_entry_count or self.latest_accepted_count or self.latest_ready_count or self.latest_blocked_count):
            raise ValidationError("empty runtime registry history summary has latest data")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history summary crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("runtime registry history summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary:
        value = _mapping(value, "runtime registry history summary")
        _strict(value, set(cls.FIELDS), "runtime registry history summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary):
        raise ValidationError("runtime registry history summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory:
    """Deterministic append-only history of one registry identity."""

    FIELDS = HISTORY_FIELDS

    def __init__(self, history_id: str, registry_id: str, version: str, boundary: str, entry_count: int, latest_registry_address: str, latest_entry_count: int, latest_accepted_count: int, latest_ready_count: int, latest_blocked_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, state: str, accepted: bool, manifest: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest | Mapping[str, Any], summary: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary | Mapping[str, Any], entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.history_id = _label(history_id, "runtime registry history ID")
        self.registry_id = _label(registry_id, "runtime registry history registry ID", required=False)
        self.version = _text(version, "runtime registry history version")
        self.boundary = _text(boundary, "runtime registry history boundary")
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry.from_mapping(item) for item in _sequence(entries, "runtime registry history entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "runtime registry history entry count", MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "runtime registry history latest registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.latest_entry_count = _count(latest_entry_count, "runtime registry history latest entry count", registry_model.MAX_ENTRIES)
        self.latest_accepted_count = _count(latest_accepted_count, "runtime registry history latest accepted count", registry_model.MAX_ENTRIES)
        self.latest_ready_count = _count(latest_ready_count, "runtime registry history latest ready count", registry_model.MAX_ENTRIES)
        self.latest_blocked_count = _count(latest_blocked_count, "runtime registry history latest blocked count", registry_model.MAX_ENTRIES)
        self.initial_count = _count(initial_count, "runtime registry history initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "runtime registry history improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "runtime registry history regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "runtime registry history unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "runtime registry history changed count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("runtime registry history state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry history acceptance")
        self.manifest = manifest if isinstance(manifest, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary.from_mapping(summary)
        self.content_address = _address(content_address, "runtime registry history address", HISTORY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime registry history version or boundary is not current")
        if self.entry_count != len(self.entries) or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("runtime registry history entry order is not conserved")
        if len({item.registry_address for item in self.entries}) != len(self.entries):
            raise ValidationError("runtime registry history registry addresses must be unique")
        if self.registry_id != (self.entries[0].registry_id if self.entries else ""):
            raise ValidationError("runtime registry history identity does not replay")
        for index, item in enumerate(self.entries):
            previous = self.entries[index - 1] if index else None
            if previous is not None and item.previous_registry_address != previous.registry_address:
                raise ValidationError("runtime registry history ancestry does not link")
            if item.transition != _transition(item, previous):
                raise ValidationError("runtime registry history transition does not replay")
        latest = self.entries[-1] if self.entries else None
        expected_latest = (latest.registry_address, latest.entry_count, latest.accepted_count, latest.ready_count, latest.blocked_count) if latest else ("", 0, 0, 0, 0)
        if (self.latest_registry_address, self.latest_entry_count, self.latest_accepted_count, self.latest_ready_count, self.latest_blocked_count) != expected_latest:
            raise ValidationError("runtime registry history latest snapshot does not replay")
        transition_counts = tuple(sum(item.transition == transition for item in self.entries) for transition in TRANSITIONS)
        if transition_counts != (self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count):
            raise ValidationError("runtime registry history transition counts do not replay")
        expected_state = latest.state if latest else "empty"
        expected_accepted = latest.accepted if latest else False
        if (self.state, self.accepted) != (expected_state, expected_accepted):
            raise ValidationError("runtime registry history disposition does not replay")
        if (self.manifest.history_id, self.manifest.registry_id, self.manifest.version, self.manifest.boundary, self.manifest.files, tuple(self.manifest.artifact_addresses)) != (self.history_id, self.registry_id, VERSION, BOUNDARY, FILES, (address_entries(self.entries), self.summary.content_address)):
            raise ValidationError("runtime registry history manifest does not replay")
        summary_values = tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1])
        expected_summary = (self.history_id, self.registry_id, self.entry_count, self.latest_registry_address, self.latest_entry_count, self.latest_accepted_count, self.latest_ready_count, self.latest_blocked_count, self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count, self.state, self.accepted)
        if summary_values != expected_summary:
            raise ValidationError("runtime registry history summary does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("runtime registry history address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "registry_id": self.registry_id,
            "version": self.version,
            "boundary": self.boundary,
            "entry_count": self.entry_count,
            "latest_registry_address": self.latest_registry_address,
            "latest_entry_count": self.latest_entry_count,
            "latest_accepted_count": self.latest_accepted_count,
            "latest_ready_count": self.latest_ready_count,
            "latest_blocked_count": self.latest_blocked_count,
            "initial_count": self.initial_count,
            "improved_count": self.improved_count,
            "regressed_count": self.regressed_count,
            "unchanged_count": self.unchanged_count,
            "changed_count": self.changed_count,
            "state": self.state,
            "accepted": self.accepted,
            "manifest": self.manifest.to_dict(),
            "summary": self.summary.to_dict(),
            "entries": [item.to_dict() for item in self.entries],
            "content_address": self.content_address,
        }

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "summary", "entries"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory:
        value = _mapping(value, "runtime registry history")
        _strict(value, set(cls.FIELDS), "runtime registry history")
        return cls(*(value[field] for field in cls.FIELDS))


def address_history(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory):
        raise ValidationError("runtime registry history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def build_history(registries: Sequence[registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry], *, history_id: str = DEFAULT_HISTORY_ID) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory:
    typed = tuple(_sequence(registries, "runtime registry history registries", MAX_ENTRIES))
    if any(not isinstance(item, registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry) for item in typed):
        raise ValidationError("runtime registry history requires typed registries")
    for item in typed:
        registry_model.verify_registry(item)
    identities = {item.registry_id for item in typed}
    if len(identities) > 1:
        raise ValidationError("runtime registry history cannot mix registry identities")
    if len({item.content_address for item in typed}) != len(typed):
        raise ValidationError("runtime registry history cannot repeat registry addresses")
    registry_id = next(iter(identities), "")
    entries: list[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry] = []
    previous: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry | None = None
    for ordinal, value in enumerate(typed, 1):
        transition = _transition(value, previous)
        current = entry_from_registry(value, ordinal, transition, previous.registry_address if previous else "")
        entries.append(current)
        previous = current
    latest = entries[-1] if entries else None
    transition_counts = {f"{transition}_count": sum(item.transition == transition for item in entries) for transition in TRANSITIONS}
    summary_body = {
        "history_id": history_id,
        "registry_id": registry_id,
        "entry_count": len(entries),
        "latest_registry_address": latest.registry_address if latest else "",
        "latest_entry_count": latest.entry_count if latest else 0,
        "latest_accepted_count": latest.accepted_count if latest else 0,
        "latest_ready_count": latest.ready_count if latest else 0,
        "latest_blocked_count": latest.blocked_count if latest else 0,
        **transition_counts,
        "state": latest.state if latest else "empty",
        "accepted": latest.accepted if latest else False,
        "content_address": SUMMARY_PREFIX + ":pending",
    }
    summary_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary(**summary_body)
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    entries_address = address_entries(entries)
    manifest_body = {
        "history_id": history_id,
        "registry_id": registry_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "files": FILES,
        "artifact_addresses": (entries_address, summary.content_address),
        "content_address": MANIFEST_PREFIX + ":pending",
    }
    manifest_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest(**manifest_body)
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {
        "history_id": history_id,
        "registry_id": registry_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "entry_count": len(entries),
        "latest_registry_address": latest.registry_address if latest else "",
        "latest_entry_count": latest.entry_count if latest else 0,
        "latest_accepted_count": latest.accepted_count if latest else 0,
        "latest_ready_count": latest.ready_count if latest else 0,
        "latest_blocked_count": latest.blocked_count if latest else 0,
        **transition_counts,
        "state": latest.state if latest else "empty",
        "accepted": latest.accepted if latest else False,
        "manifest": manifest,
        "summary": summary,
        "entries": entries,
        "content_address": HISTORY_PREFIX + ":pending",
    }
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory(**(body | {"content_address": address_history(provisional)}))


def verify_history(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory):
        raise ValidationError("runtime registry history verification requires a typed history")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory.from_mapping(value.to_dict())


def history_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory.from_mapping(value)


def history_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def history_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory) -> str:
    value = verify_history(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ENTRY_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ENTRY_FIELDS) for item in value.entries)
    return output.getvalue()


def render_history_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory) -> str:
    value = verify_history(value)
    lines = [
        "# History-Diff Archive Transfer Recovery Execution Runtime Registry History",
        "",
        f"- History: {value.history_id}",
        f"- Registry: {value.registry_id}",
        f"- Snapshots: {value.entry_count}",
        f"- State: {value.state}",
        f"- Accepted: {value.accepted}",
        f"- Address: {value.content_address}",
        "",
        "| # | registry snapshot | entries | accepted | ready | blocked | transition | state |",
        "| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    lines.extend(f"| {item.ordinal} | {item.registry_address} | {item.entry_count} | {item.accepted_count} | {item.ready_count} | {item.blocked_count} | {item.transition} | {item.state} |" for item in value.entries)
    return "\n".join(lines) + "\n"


def entries_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntries) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntries.from_mapping(value.to_dict()).to_dict())


def summary_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary.from_mapping(value.to_dict()).to_dict())


def manifest_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest.from_mapping(value.to_dict()).to_dict())


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_history(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_history(value)
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("runtime registry history destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".history-diff-recovery-execution-runtime-registry-history-", dir=str(destination.parent)))
    try:
        entries = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntries(value.entries, address_entries(value.entries))
        documents = {"manifest.json": value.manifest.to_dict(), "history.json": value.to_dict(), "entries.json": entries.to_dict(), "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("runtime registry history destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("runtime registry history artifact is not valid JSON") from error
    return _mapping(value, "runtime registry history artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError("runtime registry history artifact cannot be read") from error
    if actual != canonical_json(value):
        raise ValidationError("runtime registry history artifact is not canonical")


def load_history(destination: str | Path) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory:
    destination = Path(destination)
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("runtime registry history source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)):
        raise ValidationError("runtime registry history directory must contain the exact file set")
    if any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("runtime registry history directory may contain only regular files")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        _read_canonical(destination / name, document)
        if len(canonical_json(document).encode("utf-8")) > MAX_HISTORY_BYTES:
            raise ValidationError("runtime registry history artifact exceeds its size bound")
    value = history_from_mapping(documents["history.json"])
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest.from_mapping(documents["manifest.json"])
    entries = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntries.from_mapping(documents["entries.json"])
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary.from_mapping(documents["summary.json"])
    expected_entries = {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}
    if manifest.to_dict() != value.manifest.to_dict() or entries.to_dict() != expected_entries or summary.to_dict() != value.summary.to_dict():
        raise ValidationError("runtime registry history component documents do not replay history.json")
    if tuple(manifest.artifact_addresses) != (entries.content_address, summary.content_address):
        raise ValidationError("runtime registry history manifest artifact addresses do not replay")
    return value


def run_history(registries: Sequence[registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry], *, history_id: str = DEFAULT_HISTORY_ID, destination: str | Path | None = None, overwrite: bool = False) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory:
    value = build_history(registries, history_id=history_id)
    if destination is not None:
        persist_history(value, destination, overwrite=overwrite)
    return value


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "ready_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "transition": {"enum": list(TRANSITIONS)}, "previous_registry_address": {"type": "string"}, "content_address": {"type": "string"}}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "latest_registry_address": {"type": "string"}, "latest_entry_count": {"type": "integer", "minimum": 0}, "latest_accepted_count": {"type": "integer", "minimum": 0}, "latest_ready_count": {"type": "integer", "minimum": 0}, "latest_blocked_count": {"type": "integer", "minimum": 0}, "initial_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory", "type": "object", "additionalProperties": False, "required": list(HISTORY_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "entry_count": {"type": "integer", "minimum": 0}, "latest_registry_address": {"type": "string"}, "latest_entry_count": {"type": "integer", "minimum": 0}, "latest_accepted_count": {"type": "integer", "minimum": 0}, "latest_ready_count": {"type": "integer", "minimum": 0}, "latest_blocked_count": {"type": "integer", "minimum": 0}, "initial_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "manifest": {"type": "object"}, "summary": {"type": "object"}, "entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "history_prefix": HISTORY_PREFIX, "entry_prefix": ENTRY_PREFIX, "entries_prefix": ENTRIES_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "summary_prefix": SUMMARY_PREFIX, "files": FILES, "transitions": TRANSITIONS, "states": STATES, "limits": {"max_entries": MAX_ENTRIES, "max_history_bytes": MAX_HISTORY_BYTES}, "features": ("append-only registry snapshots", "ancestry-linked addresses", "deterministic trend transitions", "state and counter conservation", "exact four-file atomic persistence", "canonical reload verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "HISTORY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_HISTORY_ID", "FILES", "ARTIFACT_FILES", "MANIFEST_ARTIFACT_FILES", "TRANSITIONS", "STATES", "MAX_ENTRIES", "MAX_HISTORY_BYTES", "ENTRY_FIELDS", "ENTRIES_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "HISTORY_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntries", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory", "address_entry", "address_entries", "address_manifest", "address_summary", "address_history", "entry_from_registry", "build_history", "verify_history", "history_from_mapping", "history_json", "history_csv", "render_history_markdown", "entries_json", "summary_json", "manifest_json", "persist_history", "load_history", "run_history", "entry_schema", "entries_schema", "manifest_schema", "summary_schema", "history_schema", "capabilities"]
