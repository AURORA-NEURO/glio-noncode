"""Deterministic admission for exact execution-ledger runtime handoffs."""

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

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

VERSION = runtime_model.VERSION + "-registry-v1"
BOUNDARY = runtime_model.BOUNDARY + "_registry"
REGISTRY_PREFIX = runtime_model.RUNTIME_PREFIX + "-registry"
ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
ENTRIES_PREFIX = REGISTRY_PREFIX + "-entries"
ARTIFACT_PREFIX = REGISTRY_PREFIX + "-artifact"
MANIFEST_PREFIX = REGISTRY_PREFIX + "-manifest"
SUMMARY_PREFIX = REGISTRY_PREFIX + "-summary"
DEFAULT_REGISTRY_ID = "runtime-registry-history-diff-archive-transfer-recovery-execution-ledger-runtime-registry"
FILES = ("manifest.json", "registry.json", "entries.json", "summary.json")
ARTIFACT_FILES = ("entries.json", "summary.json")
STATES = ("empty", "ready", "blocked")
MAX_ENTRIES = 256
MAX_REGISTRY_BYTES = 16 * 1024 * 1024
ENTRY_FIELDS = ("ordinal", "runtime_id", "runtime_address", "runtime_version", "ledger_id", "ledger_address", "ledger_audit_address", "query_address", "query_audit_address", "stage_count", "state", "accepted", "content_address")
ENTRIES_FIELDS = ("entries", "content_address")
ARTIFACT_FIELDS = ("ordinal", "name", "size", "hash", "content_address")
MANIFEST_FIELDS = ("registry_id", "version", "boundary", "files", "artifacts", "registry_address", "manifest_address")
SUMMARY_FIELDS = ("registry_id", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "content_address")
REGISTRY_FIELDS = ("registry_id", "version", "boundary", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "manifest", "summary", "entries", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong public address namespace")
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
    return runtime_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry:
    """One path-free admission row for a ledger-runtime handoff."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, runtime_id: str, runtime_address: str, runtime_version: str, ledger_id: str, ledger_address: str, ledger_audit_address: str, query_address: str, query_audit_address: str, stage_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger runtime registry entry ordinal", MAX_ENTRIES, lower=1)
        self.runtime_id = _label(runtime_id, "ledger runtime registry runtime ID")
        self.runtime_address = _address(runtime_address, "ledger runtime registry runtime address", runtime_model.RUNTIME_PREFIX)
        self.runtime_version = _text(runtime_version, "ledger runtime registry runtime version", 2048)
        self.ledger_id = _label(ledger_id, "ledger runtime registry ledger ID")
        self.ledger_address = _address(ledger_address, "ledger runtime registry ledger address")
        self.ledger_audit_address = _address(ledger_audit_address, "ledger runtime registry ledger audit address")
        self.query_address = _address(query_address, "ledger runtime registry query address")
        self.query_audit_address = _address(query_audit_address, "ledger runtime registry query audit address")
        self.stage_count = _count(stage_count, "ledger runtime registry stage count", len(runtime_model.STAGES), lower=1)
        if state not in runtime_model.STATES:
            raise ValidationError("ledger runtime registry entry state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "ledger runtime registry entry acceptance")
        if self.accepted != (self.state == "ready"):
            raise ValidationError("ledger runtime registry entry state does not replay acceptance")
        self.content_address = _address(content_address, "ledger runtime registry entry address", ENTRY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.runtime_version != runtime_model.VERSION or self.stage_count != len(runtime_model.STAGES):
            raise ValidationError("ledger runtime registry entry runtime shape is not current")
        if not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry entry crosses the public boundary")
        if not _is_pending(self.content_address) and address_entry(self) != self.content_address:
            raise ValidationError("ledger runtime registry entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry":
        value = _mapping(value, "ledger runtime registry entry")
        _strict(value, set(cls.FIELDS), "ledger runtime registry entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry):
        raise ValidationError("ledger runtime registry entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def _entry_body(value: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    return {"ordinal": ordinal, "runtime_id": value["runtime_id"], "runtime_address": value["runtime_address"], "runtime_version": value["runtime_version"], "ledger_id": value["ledger_id"], "ledger_address": value["ledger_address"], "ledger_audit_address": value["ledger_audit_address"], "query_address": value["query_address"], "query_audit_address": value["query_audit_address"], "stage_count": value["stage_count"], "state": value["state"], "accepted": value["accepted"], "content_address": "pending:ledger-runtime-registry-entry"}


def _entry_from_record(value: Mapping[str, Any], ordinal: int) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry(**_entry_body(value, ordinal))
    body = _entry_body(value, ordinal)
    body["content_address"] = address_entry(provisional)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry(**body)


def entry_from_runtime(value: runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime, ordinal: int = 1) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry:
    if not isinstance(value, runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime):
        raise ValidationError("ledger runtime registry entries require typed runtimes")
    runtime_model.verify_runtime(value)
    return _entry_from_record({"runtime_id": value.runtime_id, "runtime_address": value.content_address, "runtime_version": value.version, "ledger_id": value.ledger_id, "ledger_address": value.ledger_address, "ledger_audit_address": value.ledger_audit_address, "query_address": value.query_address, "query_audit_address": value.query_audit_address, "stage_count": value.stage_count, "state": value.state, "accepted": value.accepted}, ordinal)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntries:
    """Ordered and addressed entry projection persisted beside a registry."""

    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry.from_mapping(item) for item in _sequence(entries, "ledger runtime registry entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "ledger runtime registry entries address", ENTRIES_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("ledger runtime registry entry ordinals do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry entries cross the public boundary")
        if not _is_pending(self.content_address) and address_entries(self.entries) != self.content_address:
            raise ValidationError("ledger runtime registry entries address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntries":
        value = _mapping(value, "ledger runtime registry entries")
        _strict(value, set(cls.FIELDS), "ledger runtime registry entries")
        return cls(tuple(value["entries"]), value["content_address"])


def address_entries(value: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry) for item in typed):
        raise ValidationError("ledger runtime registry entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact:
    """A byte receipt for one persisted registry projection."""

    FIELDS = ARTIFACT_FIELDS

    def __init__(self, ordinal: int, name: str, size: int, hash: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger runtime registry artifact ordinal", len(ARTIFACT_FILES), lower=1)
        if name not in ARTIFACT_FILES:
            raise ValidationError("ledger runtime registry artifact name is unsupported")
        self.name = name
        self.size = _count(size, "ledger runtime registry artifact size", MAX_REGISTRY_BYTES, lower=1)
        self.hash = _address(hash, "ledger runtime registry artifact hash", ARTIFACT_PREFIX)
        self.content_address = _address(content_address, "ledger runtime registry artifact address", ARTIFACT_PREFIX, allow_pending=True)
        if not _is_pending(self.content_address) and address_artifact(self) != self.content_address:
            raise ValidationError("ledger runtime registry artifact address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact":
        value = _mapping(value, "ledger runtime registry artifact")
        _strict(value, set(cls.FIELDS), "ledger runtime registry artifact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_artifact(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact):
        raise ValidationError("ledger runtime registry artifact address requires a typed artifact")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARTIFACT_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest:
    """The exact-file manifest for a persisted runtime registry."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact | Mapping[str, Any]], registry_address: str, manifest_address: str) -> None:
        self.registry_id = _label(registry_id, "ledger runtime registry manifest ID")
        self.version = _text(version, "ledger runtime registry manifest version", 2048)
        self.boundary = _text(boundary, "ledger runtime registry manifest boundary", 1024)
        if tuple(files) != FILES:
            raise ValidationError("ledger runtime registry manifest file order is not canonical")
        self.files = tuple(files)
        self.artifacts = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact.from_mapping(item) for item in _sequence(artifacts, "ledger runtime registry manifest artifacts", len(ARTIFACT_FILES)))
        if tuple(item.ordinal for item in self.artifacts) != tuple(range(1, len(ARTIFACT_FILES) + 1)) or tuple(item.name for item in self.artifacts) != ARTIFACT_FILES:
            raise ValidationError("ledger runtime registry manifest artifacts are not ordered")
        self.registry_address = _address(registry_address, "ledger runtime registry manifest registry address", REGISTRY_PREFIX)
        self.manifest_address = _address(manifest_address, "ledger runtime registry manifest address", MANIFEST_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry manifest is not current and public")
        if not _is_pending(self.manifest_address) and address_manifest(self) != self.manifest_address:
            raise ValidationError("ledger runtime registry manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "files": self.files, "artifacts": [item.to_dict() for item in self.artifacts], "registry_address": self.registry_address, "manifest_address": self.manifest_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest":
        value = _mapping(value, "ledger runtime registry manifest")
        _strict(value, set(cls.FIELDS), "ledger runtime registry manifest")
        return cls(value["registry_id"], value["version"], value["boundary"], tuple(value["files"]), tuple(value["artifacts"]), value["registry_address"], value["manifest_address"])


def address_manifest(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest):
        raise ValidationError("ledger runtime registry manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary:
    """Conserved counts and folded state for a ledger-runtime registry."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, registry_id: str, entry_count: int, accepted_count: int, ready_count: int, blocked_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.registry_id = _label(registry_id, "ledger runtime registry summary ID")
        self.entry_count = _count(entry_count, "ledger runtime registry summary entry count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "ledger runtime registry summary accepted count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "ledger runtime registry summary ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "ledger runtime registry summary blocked count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("ledger runtime registry summary state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "ledger runtime registry summary acceptance")
        self.content_address = _address(content_address, "ledger runtime registry summary address", SUMMARY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count > self.entry_count or self.ready_count + self.blocked_count != self.entry_count:
            raise ValidationError("ledger runtime registry summary counts do not conserve")
        if self.state != ("empty" if self.entry_count == 0 else "ready" if self.blocked_count == 0 else "blocked"):
            raise ValidationError("ledger runtime registry summary state does not replay")
        if self.accepted != (self.entry_count == 0 or self.accepted_count == self.entry_count):
            raise ValidationError("ledger runtime registry summary acceptance does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry summary crosses the public boundary")
        if not _is_pending(self.content_address) and address_summary(self) != self.content_address:
            raise ValidationError("ledger runtime registry summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary":
        value = _mapping(value, "ledger runtime registry summary")
        _strict(value, set(cls.FIELDS), "ledger runtime registry summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary):
        raise ValidationError("ledger runtime registry summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


def _state(entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry]) -> str:
    return "empty" if not entries else "ready" if all(item.accepted for item in entries) else "blocked"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry:
    """Deterministic multi-runtime admission for ledger-runtime handoffs."""

    FIELDS = REGISTRY_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, entry_count: int, accepted_count: int, ready_count: int, blocked_count: int, state: str, accepted: bool, manifest: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest | Mapping[str, Any], summary: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary | Mapping[str, Any], entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.registry_id = _label(registry_id, "ledger runtime registry ID")
        self.version = _text(version, "ledger runtime registry version", 2048)
        self.boundary = _text(boundary, "ledger runtime registry boundary", 1024)
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry.from_mapping(item) for item in _sequence(entries, "ledger runtime registry entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "ledger runtime registry entry count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "ledger runtime registry accepted count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "ledger runtime registry ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "ledger runtime registry blocked count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("ledger runtime registry state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "ledger runtime registry acceptance")
        self.manifest = manifest if isinstance(manifest, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary.from_mapping(summary)
        self.content_address = _address(content_address, "ledger runtime registry address", REGISTRY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        keys = tuple((item.runtime_id, item.runtime_address) for item in self.entries)
        expected_accepted = sum(item.accepted for item in self.entries)
        expected_ready = sum(item.state == "ready" for item in self.entries)
        expected_blocked = sum(item.state == "blocked" for item in self.entries)
        expected_state = _state(self.entries)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger runtime registry version or boundary is not current")
        if self.entry_count != len(self.entries) or len(keys) != len(set(keys)) or keys != tuple(sorted(keys)):
            raise ValidationError("ledger runtime registry identities are not unique or ordered")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("ledger runtime registry ordinals do not replay")
        if (self.accepted_count, self.ready_count, self.blocked_count, self.state) != (expected_accepted, expected_ready, expected_blocked, expected_state):
            raise ValidationError("ledger runtime registry counts or state do not replay")
        if self.accepted != (not self.entries or expected_accepted == self.entry_count):
            raise ValidationError("ledger runtime registry acceptance does not replay")
        if (self.manifest.registry_id, self.manifest.version, self.manifest.boundary, self.manifest.files, tuple(item.name for item in self.manifest.artifacts), self.manifest.registry_address) != (self.registry_id, self.version, self.boundary, FILES, ARTIFACT_FILES, self.content_address):
            raise ValidationError("ledger runtime registry manifest does not replay")
        if (self.summary.registry_id, self.summary.entry_count, self.summary.accepted_count, self.summary.ready_count, self.summary.blocked_count, self.summary.state, self.summary.accepted) != (self.registry_id, self.entry_count, self.accepted_count, self.ready_count, self.blocked_count, self.state, self.accepted):
            raise ValidationError("ledger runtime registry summary does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger runtime registry crosses the public boundary")
        if not _is_pending(self.content_address) and address_registry(self) != self.content_address:
            raise ValidationError("ledger runtime registry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "accepted_count": self.accepted_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "state": self.state, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("registry_id", "version", "boundary", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry":
        value = _mapping(value, "ledger runtime registry")
        _strict(value, set(cls.FIELDS), "ledger runtime registry")
        return cls(value["registry_id"], value["version"], value["boundary"], value["entry_count"], value["accepted_count"], value["ready_count"], value["blocked_count"], value["state"], value["accepted"], value["manifest"], value["summary"], tuple(value["entries"]), value["content_address"])


def address_registry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry):
        raise ValidationError("ledger runtime registry address requires a typed registry")
    # The manifest records this address and is itself nested in registry.json.
    # Excluding that circular metadata keeps the registry identity stable while
    # the manifest independently authenticates the persisted projections.
    return content_hash(value.to_dict() | {"manifest": None, "content_address": None}, prefix=REGISTRY_PREFIX)


def _registry_from_entries(registry_id: str, records: Sequence[Mapping[str, Any]]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry:
    ordered_records = tuple(sorted(records, key=lambda item: (item["runtime_id"], item["runtime_address"])))
    if len(ordered_records) > MAX_ENTRIES:
        raise ValidationError("ledger runtime registry exceeds its entry bound")
    identities = tuple((item["runtime_id"], item["runtime_address"]) for item in ordered_records)
    if len(identities) != len(set(identities)):
        raise ValidationError("ledger runtime registry runtime identities must be unique")
    entries = tuple(_entry_from_record(item, ordinal) for ordinal, item in enumerate(ordered_records, 1))
    entry_count = len(entries)
    accepted_count = sum(item.accepted for item in entries)
    ready_count = sum(item.state == "ready" for item in entries)
    blocked_count = sum(item.state == "blocked" for item in entries)
    state = _state(entries)
    accepted = not entries or accepted_count == entry_count
    summary_body = {"registry_id": registry_id, "entry_count": entry_count, "accepted_count": accepted_count, "ready_count": ready_count, "blocked_count": blocked_count, "state": state, "accepted": accepted, "content_address": "pending:ledger-runtime-registry-summary"}
    summary_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary(**summary_body)
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    body = {"registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": entry_count, "accepted_count": accepted_count, "ready_count": ready_count, "blocked_count": blocked_count, "state": state, "accepted": accepted, "summary": summary, "entries": entries}
    provisional_manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest(registry_id, VERSION, BOUNDARY, FILES, tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact(index, name, 1, ARTIFACT_PREFIX + ":pending", "pending:ledger-runtime-registry-artifact") for index, name in enumerate(ARTIFACT_FILES, 1)), REGISTRY_PREFIX + ":pending", "pending:ledger-runtime-registry-manifest")
    # The manifest is rebuilt after the registry address is known; pending artifact receipts are valid only during construction.
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry(**(body | {"manifest": provisional_manifest}), content_address=REGISTRY_PREFIX + ":pending")
    entries_address = address_entries(entries)
    provisional_files = {"registry.json": canonical_bytes(provisional.to_dict()), "entries.json": canonical_bytes(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntries(entries, entries_address).to_dict()), "summary.json": canonical_bytes(summary.to_dict())}
    artifacts_pending = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact(index, name, len(provisional_files[name]), hash_bytes(provisional_files[name], prefix=ARTIFACT_PREFIX), "pending:ledger-runtime-registry-artifact") for index, name in enumerate(ARTIFACT_FILES, 1))
    artifacts = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact(item.ordinal, item.name, item.size, item.hash, address_artifact(item)) for item in artifacts_pending)
    manifest_body = {"registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": artifacts, "registry_address": address_registry(provisional)}
    manifest_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest(**manifest_body, manifest_address="pending:ledger-runtime-registry-manifest")
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest(**manifest_body, manifest_address=address_manifest(manifest_provisional))
    body["manifest"] = manifest
    final_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry(**body, content_address=address_registry(provisional))
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry(**body, content_address=address_registry(final_provisional))


def build_registry(runtimes: Sequence[runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime], *, registry_id: str = DEFAULT_REGISTRY_ID) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry:
    runtimes = tuple(_sequence(runtimes, "ledger runtime registry runtimes", MAX_ENTRIES))
    if any(not isinstance(item, runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime) for item in runtimes):
        raise ValidationError("ledger runtime registry requires typed runtimes")
    records = []
    for item in runtimes:
        records.append(entry_from_runtime(item).to_dict())
    return _registry_from_entries(registry_id, records)


def admit_runtime(registry: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry, runtime: runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry:
    """Return a new registry with one runtime admitted copy-on-write."""
    registry = verify_registry(registry)
    incoming = entry_from_runtime(runtime)
    identities = {(item.runtime_id, item.runtime_address) for item in registry.entries}
    if (incoming.runtime_id, incoming.runtime_address) in identities:
        raise ValidationError("ledger runtime registry refuses a duplicate runtime identity")
    records = [item.to_dict() for item in registry.entries] + [incoming.to_dict()]
    return _registry_from_entries(registry.registry_id, records)


def admit_runtimes(registry: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry, runtimes: Sequence[runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry:
    result = verify_registry(registry)
    for item in _sequence(runtimes, "ledger runtime registry runtimes", MAX_ENTRIES):
        result = admit_runtime(result, item)
    return result


def verify_registry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry):
        raise ValidationError("ledger runtime registry verification requires a typed registry")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry.from_mapping(value.to_dict())


def registry_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry.from_mapping(value)


def registry_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) -> str:
    return canonical_json(verify_registry(value).to_dict())


def registry_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) -> str:
    value = verify_registry(value)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("field", "value"))
    for field in ("registry_id", "version", "boundary", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "content_address"):
        writer.writerow((field, json.dumps(getattr(value, field), ensure_ascii=False, sort_keys=True)))
    return stream.getvalue()


def entries_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntries) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntries.from_mapping(value.to_dict()).to_dict())


def summary_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary.from_mapping(value.to_dict()).to_dict())


def manifest_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest.from_mapping(value.to_dict()).to_dict())


def render_registry_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) -> str:
    value = verify_registry(value)
    lines = ["# Exact execution ledger runtime registry", "", f"- Registry: `{value.registry_id}`", f"- State: `{value.state}`", f"- Entries: `{value.entry_count}`", f"- Accepted: `{value.accepted_count}/{value.entry_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | runtime | state | accepted | ledger | runtime address |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.runtime_id}` | `{item.state}` | `{item.accepted}` | `{item.ledger_id}` | `{item.runtime_address}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def _documents(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) -> dict[str, bytes]:
    entries = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntries(value.entries, address_entries(value.entries))
    return {"registry.json": canonical_bytes(value.to_dict()), "entries.json": canonical_bytes(entries.to_dict()), "summary.json": canonical_bytes(value.summary.to_dict())}


def _manifest_for_documents(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry, documents: Mapping[str, bytes]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest:
    receipts_pending = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact(index, name, len(documents[name]), hash_bytes(documents[name], prefix=ARTIFACT_PREFIX), "pending:ledger-runtime-registry-artifact") for index, name in enumerate(ARTIFACT_FILES, 1))
    receipts = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact(item.ordinal, item.name, item.size, item.hash, address_artifact(item)) for item in receipts_pending)
    body = {"registry_id": value.registry_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": receipts, "registry_address": value.content_address}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest(**body, manifest_address="pending:ledger-runtime-registry-manifest")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest(**body, manifest_address=address_manifest(provisional))


def persist_registry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_registry(value)
    documents = _documents(value)
    manifest = _manifest_for_documents(value, documents)
    members = {"manifest.json": canonical_bytes(manifest.to_dict()), **documents}
    target = Path(destination)
    if target.exists():
        if not overwrite or target.is_symlink() or not target.is_dir():
            raise ValidationError("ledger runtime registry destination exists; explicit overwrite is required")
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
        raise ValidationError("ledger runtime registry could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = _mapping(json.loads(raw.decode("utf-8")), f"ledger runtime registry member {path.name}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"ledger runtime registry member {path.name} is not valid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"ledger runtime registry member {path.name} is not canonical")
    if len(raw) > MAX_REGISTRY_BYTES:
        raise ValidationError(f"ledger runtime registry member {path.name} exceeds its size bound")
    return value, raw


def load_registry(destination: str | Path) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry:
    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("ledger runtime registry source must be a regular directory")
    children = tuple(root.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("ledger runtime registry directory has an unexpected file set")
    documents: dict[str, Mapping[str, Any]] = {}
    raw_documents: dict[str, bytes] = {}
    for name in FILES:
        documents[name], raw_documents[name] = _read_json(root / name)
    value = registry_from_mapping(documents["registry.json"])
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest.from_mapping(documents["manifest.json"])
    entries = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntries.from_mapping(documents["entries.json"])
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary.from_mapping(documents["summary.json"])
    if manifest.to_dict() != value.manifest.to_dict() or tuple(item.to_dict() for item in entries.entries) != tuple(item.to_dict() for item in value.entries) or entries.content_address != address_entries(value.entries) or summary.to_dict() != value.summary.to_dict():
        raise ValidationError("ledger runtime registry component documents do not replay registry.json")
    expected_documents = _documents(value)
    expected_manifest = _manifest_for_documents(value, expected_documents)
    expected_members = {"manifest.json": canonical_bytes(expected_manifest.to_dict()), **expected_documents}
    if manifest.to_dict() != expected_manifest.to_dict() or raw_documents["manifest.json"] != expected_members["manifest.json"]:
        raise ValidationError("ledger runtime registry manifest does not replay")
    for name in FILES:
        if raw_documents[name] != expected_members[name]:
            raise ValidationError(f"ledger runtime registry member {name} does not replay")
    for receipt in manifest.artifacts:
        raw = expected_members[receipt.name]
        expected = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact(receipt.ordinal, receipt.name, len(raw), hash_bytes(raw, prefix=ARTIFACT_PREFIX), "pending:ledger-runtime-registry-artifact")
        if receipt.size != expected.size or receipt.hash != expected.hash or receipt.content_address != address_artifact(expected):
            raise ValidationError("ledger runtime registry artifact receipt does not replay")
    return verify_registry(value)


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "runtime_id": {"type": "string"}, "runtime_address": {"type": "string", "pattern": "^" + runtime_model.RUNTIME_PREFIX + ":"}, "runtime_version": {"type": "string", "const": runtime_model.VERSION}, "ledger_id": {"type": "string"}, "ledger_address": {"type": "string"}, "ledger_audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "stage_count": {"type": "integer", "const": len(runtime_model.STAGES)}, "state": {"type": "string", "enum": list(runtime_model.STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + ENTRY_PREFIX + ":"}}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry entries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string", "pattern": "^" + ENTRIES_PREFIX + ":"}}}


def artifact_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry artifact", "type": "object", "additionalProperties": False, "required": list(ARTIFACT_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": len(ARTIFACT_FILES)}, "name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"registry_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": artifact_schema(), "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES)}, "registry_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"registry_id": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "ready_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + SUMMARY_PREFIX + ":"}}}


def registry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry", "type": "object", "additionalProperties": False, "required": list(REGISTRY_FIELDS), "properties": {"registry_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "ready_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "manifest": manifest_schema(), "summary": summary_schema(), "entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "registry_prefix": REGISTRY_PREFIX, "entry_prefix": ENTRY_PREFIX, "entries_prefix": ENTRIES_PREFIX, "artifact_prefix": ARTIFACT_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "summary_prefix": SUMMARY_PREFIX, "files": FILES, "artifact_files": ARTIFACT_FILES, "states": STATES, "max_entries": MAX_ENTRIES, "operations": ("build_registry", "admit_runtime", "admit_runtimes", "verify_registry", "registry_from_mapping", "persist_registry", "load_registry", "registry_json", "registry_csv", "render_registry_markdown", "entries_json", "summary_json", "manifest_json"), "features": ("deterministic identity order", "duplicate identity rejection", "empty ready and blocked folding", "copy-on-write admission", "exact four-file atomic persistence", "manifest byte receipts", "canonical reload verification"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["VERSION", "BOUNDARY", "REGISTRY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "ARTIFACT_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_REGISTRY_ID", "FILES", "ARTIFACT_FILES", "STATES", "MAX_ENTRIES", "MAX_REGISTRY_BYTES", "ENTRY_FIELDS", "ENTRIES_FIELDS", "ARTIFACT_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "REGISTRY_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntry", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryEntries", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryArtifact", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryManifest", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry", "address_entry", "address_entries", "address_artifact", "address_manifest", "address_summary", "address_registry", "entry_from_runtime", "build_registry", "admit_runtime", "admit_runtimes", "verify_registry", "registry_from_mapping", "registry_json", "registry_csv", "entries_json", "summary_json", "manifest_json", "render_registry_markdown", "persist_registry", "load_registry", "entry_schema", "entries_schema", "artifact_schema", "manifest_schema", "summary_schema", "registry_schema", "capabilities"]
