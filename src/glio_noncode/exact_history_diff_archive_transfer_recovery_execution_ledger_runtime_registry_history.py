"""Append-only history for exact execution-ledger runtime registries."""

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

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

VERSION = registry_model.VERSION + "-history-v1"
BOUNDARY = registry_model.BOUNDARY + "_history"
HISTORY_PREFIX = registry_model.REGISTRY_PREFIX + "-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
ENTRIES_PREFIX = HISTORY_PREFIX + "-entries"
ARTIFACT_PREFIX = HISTORY_PREFIX + "-artifact"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
SUMMARY_PREFIX = HISTORY_PREFIX + "-summary"
DEFAULT_HISTORY_ID = HISTORY_PREFIX
FILES = ("manifest.json", "history.json", "entries.json", "summary.json")
ARTIFACT_FILES = ("entries.json", "summary.json")
TRANSITIONS = ("initial", "improved", "regressed", "unchanged", "changed")
STATES = registry_model.STATES
MAX_ENTRIES = registry_model.MAX_ENTRIES
MAX_HISTORY_BYTES = 16 * 1024 * 1024
ENTRY_FIELDS = ("ordinal", "registry_id", "registry_address", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "transition", "previous_registry_address", "content_address")
ENTRIES_FIELDS = ("entries", "content_address")
ARTIFACT_FIELDS = ("ordinal", "name", "size", "hash", "content_address")
MANIFEST_FIELDS = ("history_id", "registry_id", "version", "boundary", "files", "artifacts", "history_address", "manifest_address")
SUMMARY_FIELDS = ("history_id", "registry_id", "entry_count", "latest_registry_address", "latest_entry_count", "latest_accepted_count", "latest_ready_count", "latest_blocked_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "state", "accepted", "content_address")
HISTORY_FIELDS = ("history_id", "registry_id", "version", "boundary", "entry_count", "latest_registry_address", "latest_entry_count", "latest_accepted_count", "latest_ready_count", "latest_blocked_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "state", "accepted", "manifest", "summary", "entries", "content_address")


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
    value = _text(value, field, required=required)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if value and (":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has the wrong public address namespace")
    if required and not value:
        raise ValidationError(f"{field} is required")
    return value


def _is_pending(value: str) -> bool:
    return value.startswith("pending:") or value.endswith(":pending")


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
    if isinstance(value, Mapping):
        return all(key not in {"source_path", "source_paths", "source_record", "source_records", "raw_bytes", "private_fields"} and _public(item) for key, item in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return True


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


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry:
    """One addressed public registry snapshot in append order."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, registry_id: str, registry_address: str, entry_count: int, accepted_count: int, ready_count: int, blocked_count: int, state: str, accepted: bool, transition: str, previous_registry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger runtime registry history entry ordinal", MAX_ENTRIES, lower=1)
        self.registry_id = _label(registry_id, "ledger runtime registry history entry registry ID")
        self.registry_address = _address(registry_address, "ledger runtime registry history entry registry address", registry_model.REGISTRY_PREFIX)
        self.entry_count = _count(entry_count, "ledger runtime registry history entry count", registry_model.MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "ledger runtime registry history accepted count", registry_model.MAX_ENTRIES)
        self.ready_count = _count(ready_count, "ledger runtime registry history ready count", registry_model.MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "ledger runtime registry history blocked count", registry_model.MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("ledger runtime registry history entry state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "ledger runtime registry history entry acceptance")
        self.transition = _label(transition, "ledger runtime registry history entry transition")
        if self.transition not in TRANSITIONS:
            raise ValidationError("ledger runtime registry history entry transition is unsupported")
        self.previous_registry_address = _address(previous_registry_address, "ledger runtime registry history previous registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.content_address = _address(content_address, "ledger runtime registry history entry address", ENTRY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count > self.entry_count or self.ready_count + self.blocked_count != self.entry_count:
            raise ValidationError("ledger runtime registry history entry counts are inconsistent")
        if self.state != _state(self.entry_count, self.ready_count, self.blocked_count):
            raise ValidationError("ledger runtime registry history entry state does not replay")
        if self.accepted != (not self.entry_count or self.accepted_count == self.entry_count):
            raise ValidationError("ledger runtime registry history entry acceptance does not replay")
        if self.ordinal == 1 and (self.transition != "initial" or self.previous_registry_address):
            raise ValidationError("first ledger runtime registry history entry must be initial")
        if self.ordinal > 1 and (self.transition == "initial" or not self.previous_registry_address):
            raise ValidationError("later ledger runtime registry history entries require ancestry")
        if not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry history entry crosses the public boundary")
        if not _is_pending(self.content_address) and address_entry(self) != self.content_address:
            raise ValidationError("ledger runtime registry history entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry":
        value = _mapping(value, "ledger runtime registry history entry")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry):
        raise ValidationError("ledger runtime registry history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def entry_from_registry(value: registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry, ordinal: int, transition: str, previous_registry_address: str = "") -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry:
    if not isinstance(value, registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry):
        raise ValidationError("ledger runtime registry history entries require typed registries")
    value = registry_model.verify_registry(value)
    body = {"ordinal": ordinal, "registry_id": value.registry_id, "registry_address": value.content_address, "entry_count": value.entry_count, "accepted_count": value.accepted_count, "ready_count": value.ready_count, "blocked_count": value.blocked_count, "state": value.state, "accepted": value.accepted, "transition": transition, "previous_registry_address": previous_registry_address, "content_address": "pending:ledger-runtime-registry-history-entry"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry(**(body | {"content_address": address_entry(provisional)}))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntries:
    """Ordered and addressed snapshot projection persisted beside a history."""

    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry.from_mapping(item) for item in _sequence(entries, "ledger runtime registry history entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "ledger runtime registry history entries address", ENTRIES_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry history entries cross the public boundary")
        if not _is_pending(self.content_address) and address_entries(self.entries) != self.content_address:
            raise ValidationError("ledger runtime registry history entries address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntries":
        value = _mapping(value, "ledger runtime registry history entries")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history entries")
        return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry) for item in typed):
        raise ValidationError("ledger runtime registry history entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact:
    """A byte receipt for a persisted history projection."""

    FIELDS = ARTIFACT_FIELDS

    def __init__(self, ordinal: int, name: str, size: int, hash: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger runtime registry history artifact ordinal", len(ARTIFACT_FILES), lower=1)
        self.name = _label(name, "ledger runtime registry history artifact name")
        if self.name not in ARTIFACT_FILES:
            raise ValidationError("ledger runtime registry history artifact name is unsupported")
        self.size = _count(size, "ledger runtime registry history artifact size", MAX_HISTORY_BYTES, lower=1)
        self.hash = _address(hash, "ledger runtime registry history artifact hash", ARTIFACT_PREFIX)
        self.content_address = _address(content_address, "ledger runtime registry history artifact address", ARTIFACT_PREFIX, allow_pending=True)
        if not _is_pending(self.content_address) and address_artifact(self) != self.content_address:
            raise ValidationError("ledger runtime registry history artifact address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact":
        value = _mapping(value, "ledger runtime registry history artifact")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history artifact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_artifact(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact):
        raise ValidationError("ledger runtime registry history artifact address requires a typed artifact")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARTIFACT_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest:
    """Canonical file, address, and byte-receipt manifest for a history."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, history_id: str, registry_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact | Mapping[str, Any]], history_address: str, manifest_address: str) -> None:
        self.history_id = _label(history_id, "ledger runtime registry history manifest history ID")
        self.registry_id = _label(registry_id, "ledger runtime registry history manifest registry ID", required=False)
        self.version = _text(version, "ledger runtime registry history manifest version")
        self.boundary = _text(boundary, "ledger runtime registry history manifest boundary")
        self.files = tuple(_label(item, "ledger runtime registry history manifest file") for item in _sequence(files, "ledger runtime registry history manifest files", len(FILES)))
        self.artifacts = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact.from_mapping(item) for item in _sequence(artifacts, "ledger runtime registry history manifest artifacts", len(ARTIFACT_FILES)))
        self.history_address = _address(history_address, "ledger runtime registry history manifest history address", HISTORY_PREFIX)
        self.manifest_address = _address(manifest_address, "ledger runtime registry history manifest address", MANIFEST_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if (self.version, self.boundary, self.files, tuple(item.name for item in self.artifacts)) != (VERSION, BOUNDARY, FILES, ARTIFACT_FILES):
            raise ValidationError("ledger runtime registry history manifest does not close the public file boundary")
        if tuple(item.ordinal for item in self.artifacts) != tuple(range(1, len(ARTIFACT_FILES) + 1)) or not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry history manifest is not canonical")
        if not _is_pending(self.manifest_address) and address_manifest(self) != self.manifest_address:
            raise ValidationError("ledger runtime registry history manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "artifacts" else [item.to_dict() for item in self.artifacts] for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest":
        value = _mapping(value, "ledger runtime registry history manifest")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history manifest")
        return cls(value["history_id"], value["registry_id"], value["version"], value["boundary"], tuple(value["files"]), tuple(value["artifacts"]), value["history_address"], value["manifest_address"])


def address_manifest(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest):
        raise ValidationError("ledger runtime registry history manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary:
    """Conserved transition counters and latest snapshot disposition."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, history_id: str, registry_id: str, entry_count: int, latest_registry_address: str, latest_entry_count: int, latest_accepted_count: int, latest_ready_count: int, latest_blocked_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "ledger runtime registry history summary history ID")
        self.registry_id = _label(registry_id, "ledger runtime registry history summary registry ID", required=False)
        self.entry_count = _count(entry_count, "ledger runtime registry history summary entry count", MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "ledger runtime registry history summary latest registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.latest_entry_count = _count(latest_entry_count, "ledger runtime registry history summary latest entry count", registry_model.MAX_ENTRIES)
        self.latest_accepted_count = _count(latest_accepted_count, "ledger runtime registry history summary latest accepted count", registry_model.MAX_ENTRIES)
        self.latest_ready_count = _count(latest_ready_count, "ledger runtime registry history summary latest ready count", registry_model.MAX_ENTRIES)
        self.latest_blocked_count = _count(latest_blocked_count, "ledger runtime registry history summary latest blocked count", registry_model.MAX_ENTRIES)
        self.initial_count = _count(initial_count, "ledger runtime registry history summary initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "ledger runtime registry history summary improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "ledger runtime registry history summary regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "ledger runtime registry history summary unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "ledger runtime registry history summary changed count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("ledger runtime registry history summary state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "ledger runtime registry history summary acceptance")
        self.content_address = _address(content_address, "ledger runtime registry history summary address", SUMMARY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.latest_accepted_count > self.latest_entry_count or self.latest_ready_count + self.latest_blocked_count != self.latest_entry_count:
            raise ValidationError("ledger runtime registry history summary latest counts are inconsistent")
        if self.entry_count and self.state != _state(self.latest_entry_count, self.latest_ready_count, self.latest_blocked_count):
            raise ValidationError("ledger runtime registry history summary state does not replay")
        if not self.entry_count and (self.latest_registry_address or self.latest_entry_count or self.latest_accepted_count or self.latest_ready_count or self.latest_blocked_count):
            raise ValidationError("empty ledger runtime registry history summary has latest data")
        if not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry history summary crosses the public boundary")
        if not _is_pending(self.content_address) and address_summary(self) != self.content_address:
            raise ValidationError("ledger runtime registry history summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary":
        value = _mapping(value, "ledger runtime registry history summary")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary):
        raise ValidationError("ledger runtime registry history summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory:
    """Deterministic append-only history of one registry identity."""

    FIELDS = HISTORY_FIELDS

    def __init__(self, history_id: str, registry_id: str, version: str, boundary: str, entry_count: int, latest_registry_address: str, latest_entry_count: int, latest_accepted_count: int, latest_ready_count: int, latest_blocked_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, state: str, accepted: bool, manifest: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest | Mapping[str, Any], summary: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary | Mapping[str, Any], entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.history_id = _label(history_id, "ledger runtime registry history ID")
        self.registry_id = _label(registry_id, "ledger runtime registry history registry ID", required=False)
        self.version = _text(version, "ledger runtime registry history version")
        self.boundary = _text(boundary, "ledger runtime registry history boundary")
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry.from_mapping(item) for item in _sequence(entries, "ledger runtime registry history entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "ledger runtime registry history entry count", MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "ledger runtime registry history latest registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.latest_entry_count = _count(latest_entry_count, "ledger runtime registry history latest entry count", registry_model.MAX_ENTRIES)
        self.latest_accepted_count = _count(latest_accepted_count, "ledger runtime registry history latest accepted count", registry_model.MAX_ENTRIES)
        self.latest_ready_count = _count(latest_ready_count, "ledger runtime registry history latest ready count", registry_model.MAX_ENTRIES)
        self.latest_blocked_count = _count(latest_blocked_count, "ledger runtime registry history latest blocked count", registry_model.MAX_ENTRIES)
        self.initial_count = _count(initial_count, "ledger runtime registry history initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "ledger runtime registry history improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "ledger runtime registry history regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "ledger runtime registry history unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "ledger runtime registry history changed count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("ledger runtime registry history state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "ledger runtime registry history acceptance")
        self.manifest = manifest if isinstance(manifest, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary.from_mapping(summary)
        self.content_address = _address(content_address, "ledger runtime registry history address", HISTORY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger runtime registry history version or boundary is not current")
        if self.entry_count != len(self.entries) or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("ledger runtime registry history entry order is not conserved")
        if len({item.registry_address for item in self.entries}) != len(self.entries):
            raise ValidationError("ledger runtime registry history registry addresses must be unique")
        if self.registry_id != (self.entries[0].registry_id if self.entries else ""):
            raise ValidationError("ledger runtime registry history identity does not replay")
        for index, item in enumerate(self.entries):
            previous = self.entries[index - 1] if index else None
            if previous is not None and item.previous_registry_address != previous.registry_address:
                raise ValidationError("ledger runtime registry history ancestry does not link")
            if item.transition != _transition(item, previous):
                raise ValidationError("ledger runtime registry history transition does not replay")
        latest = self.entries[-1] if self.entries else None
        expected_latest = (latest.registry_address, latest.entry_count, latest.accepted_count, latest.ready_count, latest.blocked_count) if latest else ("", 0, 0, 0, 0)
        if (self.latest_registry_address, self.latest_entry_count, self.latest_accepted_count, self.latest_ready_count, self.latest_blocked_count) != expected_latest:
            raise ValidationError("ledger runtime registry history latest snapshot does not replay")
        transition_counts = tuple(sum(item.transition == transition for item in self.entries) for transition in TRANSITIONS)
        if transition_counts != (self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count):
            raise ValidationError("ledger runtime registry history transition counts do not replay")
        expected_state = latest.state if latest else "empty"
        expected_accepted = latest.accepted if latest else False
        if (self.state, self.accepted) != (expected_state, expected_accepted):
            raise ValidationError("ledger runtime registry history disposition does not replay")
        if (self.manifest.history_id, self.manifest.registry_id, self.manifest.version, self.manifest.boundary, self.manifest.files, tuple(item.name for item in self.manifest.artifacts), self.manifest.history_address) != (self.history_id, self.registry_id, VERSION, BOUNDARY, FILES, ARTIFACT_FILES, self.content_address):
            raise ValidationError("ledger runtime registry history manifest does not replay")
        expected_summary = (self.history_id, self.registry_id, self.entry_count, self.latest_registry_address, self.latest_entry_count, self.latest_accepted_count, self.latest_ready_count, self.latest_blocked_count, self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count, self.state, self.accepted)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected_summary:
            raise ValidationError("ledger runtime registry history summary does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry history crosses the public boundary")
        if not _is_pending(self.content_address) and address_history(self) != self.content_address:
            raise ValidationError("ledger runtime registry history address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "latest_registry_address": self.latest_registry_address, "latest_entry_count": self.latest_entry_count, "latest_accepted_count": self.latest_accepted_count, "latest_ready_count": self.latest_ready_count, "latest_blocked_count": self.latest_blocked_count, "initial_count": self.initial_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "state": self.state, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "summary", "entries"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory":
        value = _mapping(value, "ledger runtime registry history")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history")
        return cls(*(value[field] for field in cls.FIELDS))


def address_history(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory):
        raise ValidationError("ledger runtime registry history address requires a typed history")
    return content_hash(value.to_dict() | {"manifest": None, "content_address": None}, prefix=HISTORY_PREFIX)


def _summary_body(history_id: str, registry_id: str, entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry]) -> dict[str, Any]:
    latest = entries[-1] if entries else None
    counts = {f"{transition}_count": sum(item.transition == transition for item in entries) for transition in TRANSITIONS}
    return {"history_id": history_id, "registry_id": registry_id, "entry_count": len(entries), "latest_registry_address": latest.registry_address if latest else "", "latest_entry_count": latest.entry_count if latest else 0, "latest_accepted_count": latest.accepted_count if latest else 0, "latest_ready_count": latest.ready_count if latest else 0, "latest_blocked_count": latest.blocked_count if latest else 0, **counts, "state": latest.state if latest else "empty", "accepted": latest.accepted if latest else False, "content_address": "pending:ledger-runtime-registry-history-summary"}


def _compose_history(history_id: str, registry_id: str, entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory:
    entries = tuple(entries)
    summary_body = _summary_body(history_id, registry_id, entries)
    summary_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary(**summary_body)
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    entries_address = address_entries(entries)
    entries_document = canonical_bytes({"entries": [item.to_dict() for item in entries], "content_address": entries_address})
    summary_document = canonical_bytes(summary.to_dict())
    artifacts_pending = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact(index, name, len(raw), hash_bytes(raw, prefix=ARTIFACT_PREFIX), "pending:ledger-runtime-registry-history-artifact") for index, (name, raw) in enumerate((("entries.json", entries_document), ("summary.json", summary_document)), 1))
    artifacts = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact(item.ordinal, item.name, item.size, item.hash, address_artifact(item)) for item in artifacts_pending)
    manifest_body = {"history_id": history_id, "registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": artifacts, "history_address": HISTORY_PREFIX + ":pending"}
    manifest_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest(**(manifest_body | {"manifest_address": "pending:ledger-runtime-registry-history-manifest"}))
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest(**(manifest_body | {"history_address": HISTORY_PREFIX + ":pending", "manifest_address": address_manifest(manifest_provisional)}))
    latest = entries[-1] if entries else None
    body = {"history_id": history_id, "registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": len(entries), "latest_registry_address": latest.registry_address if latest else "", "latest_entry_count": latest.entry_count if latest else 0, "latest_accepted_count": latest.accepted_count if latest else 0, "latest_ready_count": latest.ready_count if latest else 0, "latest_blocked_count": latest.blocked_count if latest else 0, "initial_count": summary.initial_count, "improved_count": summary.improved_count, "regressed_count": summary.regressed_count, "unchanged_count": summary.unchanged_count, "changed_count": summary.changed_count, "state": summary.state, "accepted": summary.accepted, "manifest": manifest, "summary": summary, "entries": entries, "content_address": HISTORY_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory(**body)
    history_address = address_history(provisional)
    manifest_body["history_address"] = history_address
    manifest_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest(**(manifest_body | {"manifest_address": "pending:ledger-runtime-registry-history-manifest"}))
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest(**(manifest_body | {"manifest_address": address_manifest(manifest_provisional)}))
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory(**(body | {"manifest": manifest, "content_address": history_address}))


def build_history(registries: Sequence[registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry], *, history_id: str = DEFAULT_HISTORY_ID) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory:
    typed = tuple(_sequence(registries, "ledger runtime registry history registries", MAX_ENTRIES))
    if any(not isinstance(item, registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) for item in typed):
        raise ValidationError("ledger runtime registry history requires typed registries")
    for item in typed:
        registry_model.verify_registry(item)
    identities = {item.registry_id for item in typed}
    if len(identities) > 1:
        raise ValidationError("ledger runtime registry history cannot mix registry identities")
    if len({item.content_address for item in typed}) != len(typed):
        raise ValidationError("ledger runtime registry history cannot repeat registry addresses")
    registry_id = next(iter(identities), "")
    entries: list[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry] = []
    previous: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry | None = None
    for ordinal, registry in enumerate(typed, 1):
        current = entry_from_registry(registry, ordinal, _transition(registry, previous), previous.registry_address if previous else "")
        entries.append(current)
        previous = current
    return _compose_history(history_id, registry_id, entries)


def append_registry(history: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory, registry: registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory:
    """Return a new history with one verified registry snapshot appended."""
    history = verify_history(history)
    if not isinstance(registry, registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry):
        raise ValidationError("ledger runtime registry history append requires a typed registry")
    registry = registry_model.verify_registry(registry)
    if history.registry_id and history.registry_id != registry.registry_id:
        raise ValidationError("ledger runtime registry history append changes registry identity")
    if any(item.registry_address == registry.content_address for item in history.entries):
        raise ValidationError("ledger runtime registry history append repeats a registry address")
    current = entry_from_registry(registry, history.entry_count + 1, _transition(registry, history.entries[-1] if history.entries else None), history.entries[-1].registry_address if history.entries else "")
    return _compose_history(history.history_id, history.registry_id or registry.registry_id, history.entries + (current,))


def verify_history(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory):
        raise ValidationError("ledger runtime registry history verification requires a typed history")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory.from_mapping(value.to_dict())


def history_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory.from_mapping(value)


def history_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def history_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> str:
    value = verify_history(value)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("field", "value"))
    for field in ("history_id", "registry_id", "version", "boundary", "entry_count", "latest_registry_address", "latest_entry_count", "latest_accepted_count", "latest_ready_count", "latest_blocked_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "state", "accepted", "content_address"):
        writer.writerow((field, json.dumps(getattr(value, field), ensure_ascii=False, sort_keys=True)))
    return stream.getvalue()


def entries_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntries) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntries.from_mapping(value.to_dict()).to_dict())


def summary_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary.from_mapping(value.to_dict()).to_dict())


def manifest_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest.from_mapping(value.to_dict()).to_dict())


def render_history_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> str:
    value = verify_history(value)
    lines = ["# Exact execution ledger runtime registry history", "", f"- History: `{value.history_id}`", f"- Registry: `{value.registry_id}`", f"- State: `{value.state}`", f"- Snapshots: `{value.entry_count}`", f"- Transitions: `{value.initial_count} initial, {value.improved_count} improved, {value.regressed_count} regressed, {value.unchanged_count} unchanged, {value.changed_count} changed`", f"- Address: `{value.content_address}`", "", "| ordinal | registry address | state | accepted | transition | previous |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.registry_address}` | `{item.state}` | `{item.accepted}` | `{item.transition}` | `{item.previous_registry_address}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def _documents(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> dict[str, bytes]:
    entries = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntries(value.entries, address_entries(value.entries))
    return {"history.json": canonical_bytes(value.to_dict()), "entries.json": canonical_bytes(entries.to_dict()), "summary.json": canonical_bytes(value.summary.to_dict())}


def _manifest_for_documents(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory, documents: Mapping[str, bytes]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest:
    receipts_pending = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact(index, name, len(documents[name]), hash_bytes(documents[name], prefix=ARTIFACT_PREFIX), "pending:ledger-runtime-registry-history-artifact") for index, name in enumerate(ARTIFACT_FILES, 1))
    receipts = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact(item.ordinal, item.name, item.size, item.hash, address_artifact(item)) for item in receipts_pending)
    body = {"history_id": value.history_id, "registry_id": value.registry_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": receipts, "history_address": value.content_address}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest(**(body | {"manifest_address": "pending:ledger-runtime-registry-history-manifest"}))
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest(**(body | {"manifest_address": address_manifest(provisional)}))


def persist_history(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_history(value)
    documents = _documents(value)
    manifest = _manifest_for_documents(value, documents)
    members = {"manifest.json": canonical_bytes(manifest.to_dict()), **documents}
    target = Path(destination)
    if target.exists() and (not overwrite or target.is_symlink() or not target.is_dir()):
        raise ValidationError("ledger runtime registry history destination exists; explicit overwrite is required")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
    try:
        for name in FILES:
            (temporary / name).write_bytes(members[name])
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("ledger runtime registry history could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = _mapping(json.loads(raw.decode("utf-8")), f"ledger runtime registry history member {path.name}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"ledger runtime registry history member {path.name} is not valid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"ledger runtime registry history member {path.name} is not canonical")
    if len(raw) > MAX_HISTORY_BYTES:
        raise ValidationError(f"ledger runtime registry history member {path.name} exceeds its size bound")
    return value, raw


def load_history(destination: str | Path) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory:
    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("ledger runtime registry history source must be a regular directory")
    children = tuple(root.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("ledger runtime registry history directory has an unexpected file set")
    documents: dict[str, Mapping[str, Any]] = {}
    raw_documents: dict[str, bytes] = {}
    for name in FILES:
        documents[name], raw_documents[name] = _read_json(root / name)
    value = history_from_mapping(documents["history.json"])
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest.from_mapping(documents["manifest.json"])
    entries = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntries.from_mapping(documents["entries.json"])
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary.from_mapping(documents["summary.json"])
    if manifest.to_dict() != value.manifest.to_dict() or tuple(item.to_dict() for item in entries.entries) != tuple(item.to_dict() for item in value.entries) or entries.content_address != address_entries(value.entries) or summary.to_dict() != value.summary.to_dict():
        raise ValidationError("ledger runtime registry history component documents do not replay history.json")
    expected_documents = _documents(value)
    expected_manifest = _manifest_for_documents(value, expected_documents)
    expected_members = {"manifest.json": canonical_bytes(expected_manifest.to_dict()), **expected_documents}
    if manifest.to_dict() != expected_manifest.to_dict() or raw_documents["manifest.json"] != expected_members["manifest.json"]:
        raise ValidationError("ledger runtime registry history manifest does not replay")
    for name in FILES:
        if raw_documents[name] != expected_members[name]:
            raise ValidationError(f"ledger runtime registry history member {name} does not replay")
    for receipt in manifest.artifacts:
        raw = expected_members[receipt.name]
        expected = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact(receipt.ordinal, receipt.name, len(raw), hash_bytes(raw, prefix=ARTIFACT_PREFIX), "pending:ledger-runtime-registry-history-artifact")
        if receipt.size != expected.size or receipt.hash != expected.hash or receipt.content_address != address_artifact(expected):
            raise ValidationError("ledger runtime registry history artifact receipt does not replay")
    return verify_history(value)


def run_history(registries: Sequence[registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry], *, history_id: str = DEFAULT_HISTORY_ID, destination: str | Path | None = None, overwrite: bool = False) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory:
    value = build_history(registries, history_id=history_id)
    if destination is not None:
        persist_history(value, destination, overwrite=overwrite)
    return value


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "registry_id": {"type": "string"}, "registry_address": {"type": "string", "pattern": "^" + registry_model.REGISTRY_PREFIX + ":"}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "ready_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "transition": {"type": "string", "enum": list(TRANSITIONS)}, "previous_registry_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + ENTRY_PREFIX + ":"}}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history entries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string", "pattern": "^" + ENTRIES_PREFIX + ":"}}}


def artifact_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history artifact", "type": "object", "additionalProperties": False, "required": list(ARTIFACT_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": len(ARTIFACT_FILES)}, "name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": artifact_schema(), "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES)}, "history_address": {"type": "string", "pattern": "^" + HISTORY_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "latest_registry_address": {"type": "string"}, "latest_entry_count": {"type": "integer", "minimum": 0}, "latest_accepted_count": {"type": "integer", "minimum": 0}, "latest_ready_count": {"type": "integer", "minimum": 0}, "latest_blocked_count": {"type": "integer", "minimum": 0}, "initial_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + SUMMARY_PREFIX + ":"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history", "type": "object", "additionalProperties": False, "required": list(HISTORY_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "entry_count": {"type": "integer", "minimum": 0}, "latest_registry_address": {"type": "string"}, "latest_entry_count": {"type": "integer", "minimum": 0}, "latest_accepted_count": {"type": "integer", "minimum": 0}, "latest_ready_count": {"type": "integer", "minimum": 0}, "latest_blocked_count": {"type": "integer", "minimum": 0}, "initial_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "manifest": manifest_schema(), "summary": summary_schema(), "entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string", "pattern": "^" + HISTORY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "history_prefix": HISTORY_PREFIX, "entry_prefix": ENTRY_PREFIX, "entries_prefix": ENTRIES_PREFIX, "artifact_prefix": ARTIFACT_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "summary_prefix": SUMMARY_PREFIX, "files": FILES, "artifact_files": ARTIFACT_FILES, "transitions": TRANSITIONS, "states": STATES, "max_entries": MAX_ENTRIES, "operations": ("build_history", "append_registry", "entry_from_registry", "verify_history", "history_from_mapping", "persist_history", "load_history", "run_history", "history_json", "history_csv", "render_history_markdown", "entries_json", "summary_json", "manifest_json"), "features": ("append-only snapshot ancestry", "deterministic transition replay", "empty ready and blocked history states", "duplicate snapshot rejection", "exact four-file atomic persistence", "manifest byte receipts", "canonical reload verification"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["VERSION", "BOUNDARY", "HISTORY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "ARTIFACT_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_HISTORY_ID", "FILES", "ARTIFACT_FILES", "TRANSITIONS", "STATES", "MAX_ENTRIES", "MAX_HISTORY_BYTES", "ENTRY_FIELDS", "ENTRIES_FIELDS", "ARTIFACT_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "HISTORY_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntries", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryArtifact", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryManifest", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory", "address_entry", "address_entries", "address_artifact", "address_manifest", "address_summary", "address_history", "entry_from_registry", "build_history", "append_registry", "verify_history", "history_from_mapping", "history_json", "history_csv", "entries_json", "summary_json", "manifest_json", "render_history_markdown", "persist_history", "load_history", "run_history", "entry_schema", "entries_schema", "artifact_schema", "manifest_schema", "summary_schema", "history_schema", "capabilities"]
