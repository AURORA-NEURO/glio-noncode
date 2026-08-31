"""Deterministic admission for history-diff recovery-execution runtimes."""

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

from . import exact_history_diff_archive_transfer_recovery_execution_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-registry-v1"
BOUNDARY = runtime_model.BOUNDARY + "_registry"
REGISTRY_PREFIX = runtime_model.RUNTIME_PREFIX + "-registry"
ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
ENTRIES_PREFIX = REGISTRY_PREFIX + "-entries"
MANIFEST_PREFIX = REGISTRY_PREFIX + "-manifest"
SUMMARY_PREFIX = REGISTRY_PREFIX + "-summary"
DEFAULT_REGISTRY_ID = "history-diff-archive-transfer-recovery-execution-runtime-registry"
FILES = ("manifest.json", "registry.json", "entries.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
MANIFEST_ARTIFACT_FILES = ("entries.json", "summary.json")
MAX_ENTRIES = 256
MAX_REGISTRY_BYTES = 16 * 1024 * 1024
STATES = ("empty", "ready", "blocked")
ENTRY_FIELDS = ("ordinal", "runtime_id", "runtime_address", "runtime_version", "execution_id", "execution_address", "execution_audit_address", "query_address", "query_audit_address", "state", "accepted", "content_address")
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("registry_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("registry_id", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "content_address")
REGISTRY_FIELDS = ("registry_id", "version", "boundary", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "manifest", "summary", "entries", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
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
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
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
    return runtime_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry:
    """One path-free admission row for a history-diff runtime."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, runtime_id: str, runtime_address: str, runtime_version: str, execution_id: str, execution_address: str, execution_audit_address: str, query_address: str, query_audit_address: str, state: str, accepted: bool, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry entry ordinal", MAX_ENTRIES, lower=1)
        self.runtime_id = _label(runtime_id, "runtime registry runtime ID")
        self.runtime_address = _address(runtime_address, "runtime registry runtime address", runtime_model.RUNTIME_PREFIX)
        self.runtime_version = _text(runtime_version, "runtime registry runtime version", 1024)
        self.execution_id = _label(execution_id, "runtime registry execution ID")
        self.execution_address = _address(execution_address, "runtime registry execution address")
        self.execution_audit_address = _address(execution_audit_address, "runtime registry execution audit address")
        self.query_address = _address(query_address, "runtime registry query address")
        self.query_audit_address = _address(query_audit_address, "runtime registry query audit address")
        if state not in runtime_model.STATES:
            raise ValidationError("runtime registry entry state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry entry acceptance")
        if self.accepted != (self.state == "ready"):
            raise ValidationError("runtime registry entry state does not replay acceptance")
        self.content_address = _address(content_address, "runtime registry entry address", ENTRY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry entry crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("runtime registry entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry:
        value = _mapping(value, "runtime registry entry")
        _strict(value, set(cls.FIELDS), "runtime registry entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry):
        raise ValidationError("runtime registry entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def entry_from_runtime(value: runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntime, ordinal: int) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry:
    if not isinstance(value, runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntime):
        raise ValidationError("runtime registry entries require typed runtimes")
    runtime_model.verify_runtime(value)
    body = {"ordinal": ordinal, "runtime_id": value.runtime_id, "runtime_address": value.content_address, "runtime_version": value.version, "execution_id": value.execution_id, "execution_address": value.execution_address, "execution_audit_address": value.execution_audit_address, "query_address": value.query_address, "query_audit_address": value.query_audit_address, "state": value.state, "accepted": value.accepted, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry(**(body | {"content_address": address_entry(provisional)}))


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntries:
    """Ordered and addressed entry projection persisted beside a registry."""

    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry.from_mapping(item) for item in _sequence(entries, "runtime registry entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "runtime registry entries address", ENTRIES_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry entries cross the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_entries(self.entries) != self.content_address:
            raise ValidationError("runtime registry entries address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntries:
        value = _mapping(value, "runtime registry entries")
        _strict(value, set(cls.FIELDS), "runtime registry entries")
        return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry) for item in typed):
        raise ValidationError("runtime registry entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest:
    """Canonical file and artifact-address manifest for a runtime registry."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.registry_id = _label(registry_id, "runtime registry manifest registry ID")
        self.version = _text(version, "runtime registry manifest version", 1024)
        self.boundary = _text(boundary, "runtime registry manifest boundary", 1024)
        self.files = tuple(_label(item, "runtime registry manifest file") for item in _sequence(files, "runtime registry manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "runtime registry manifest artifact address") for item in _sequence(artifact_addresses, "runtime registry manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "runtime registry manifest address", MANIFEST_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("runtime registry manifest does not close the public file boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("runtime registry manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest:
        value = _mapping(value, "runtime registry manifest")
        _strict(value, set(cls.FIELDS), "runtime registry manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest):
        raise ValidationError("runtime registry manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary:
    """Conserved counts and folded state for a runtime registry."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, registry_id: str, entry_count: int, accepted_count: int, ready_count: int, blocked_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.registry_id = _label(registry_id, "runtime registry summary registry ID")
        self.entry_count = _count(entry_count, "runtime registry summary entry count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "runtime registry summary accepted count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "runtime registry summary ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "runtime registry summary blocked count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("runtime registry summary state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry summary acceptance")
        self.content_address = _address(content_address, "runtime registry summary address", SUMMARY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count > self.entry_count or self.ready_count + self.blocked_count != self.entry_count or not _public(self.to_dict()):
            raise ValidationError("runtime registry summary counts are inconsistent")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("runtime registry summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary:
        value = _mapping(value, "runtime registry summary")
        _strict(value, set(cls.FIELDS), "runtime registry summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary):
        raise ValidationError("runtime registry summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


def _state(entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry]) -> str:
    if not entries:
        return "empty"
    return "ready" if all(item.accepted for item in entries) else "blocked"


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry:
    """Deterministic multi-runtime admission for the target runtime family."""

    FIELDS = REGISTRY_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, entry_count: int, accepted_count: int, ready_count: int, blocked_count: int, state: str, accepted: bool, manifest: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest | Mapping[str, Any], summary: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary | Mapping[str, Any], entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.registry_id = _label(registry_id, "runtime registry ID")
        self.version = _text(version, "runtime registry version", 1024)
        self.boundary = _text(boundary, "runtime registry boundary", 1024)
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry.from_mapping(item) for item in _sequence(entries, "runtime registry entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "runtime registry entry count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "runtime registry accepted count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "runtime registry ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "runtime registry blocked count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("runtime registry state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry acceptance")
        self.manifest = manifest if isinstance(manifest, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary.from_mapping(summary)
        self.content_address = _address(content_address, "runtime registry address", REGISTRY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        keys = tuple((item.runtime_id, item.runtime_address) for item in self.entries)
        expected_accepted = sum(item.accepted for item in self.entries)
        expected_ready = sum(item.state == "ready" for item in self.entries)
        expected_blocked = sum(item.state == "blocked" for item in self.entries)
        expected_state = _state(self.entries)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime registry version or boundary is not current")
        if self.entry_count != len(self.entries) or len(keys) != len(set(keys)) or keys != tuple(sorted(keys)):
            raise ValidationError("runtime registry entry identities are not unique or ordered")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("runtime registry entry ordinals do not replay")
        if (self.accepted_count, self.ready_count, self.blocked_count, self.state) != (expected_accepted, expected_ready, expected_blocked, expected_state):
            raise ValidationError("runtime registry counts or state do not replay")
        if self.accepted != (not self.entries or expected_accepted == self.entry_count):
            raise ValidationError("runtime registry acceptance does not replay")
        if (self.manifest.registry_id, self.manifest.version, self.manifest.boundary, self.manifest.files, tuple(self.manifest.artifact_addresses)) != (self.registry_id, self.version, self.boundary, FILES, (address_entries(self.entries), self.summary.content_address)):
            raise ValidationError("runtime registry manifest does not replay")
        if (self.summary.registry_id, self.summary.entry_count, self.summary.accepted_count, self.summary.ready_count, self.summary.blocked_count, self.summary.state, self.summary.accepted) != (self.registry_id, self.entry_count, self.accepted_count, self.ready_count, self.blocked_count, self.state, self.accepted):
            raise ValidationError("runtime registry summary does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_registry(self) != self.content_address:
            raise ValidationError("runtime registry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "accepted_count": self.accepted_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "state": self.state, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("registry_id", "version", "boundary", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry:
        value = _mapping(value, "runtime registry")
        _strict(value, set(cls.FIELDS), "runtime registry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_registry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry):
        raise ValidationError("runtime registry address requires a typed registry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REGISTRY_PREFIX)


def build_registry(runtimes: Sequence[runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntime], *, registry_id: str = DEFAULT_REGISTRY_ID) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry:
    runtimes = tuple(_sequence(runtimes, "runtime registry runtimes", MAX_ENTRIES))
    if any(not isinstance(item, runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntime) for item in runtimes):
        raise ValidationError("runtime registry requires typed runtimes")
    for item in runtimes:
        runtime_model.verify_runtime(item)
    identities = tuple((item.runtime_id, item.content_address) for item in runtimes)
    if len(identities) != len(set(identities)):
        raise ValidationError("runtime registry runtime identities must be unique")
    ordered = tuple(sorted(runtimes, key=lambda item: (item.runtime_id, item.content_address)))
    entries = tuple(entry_from_runtime(item, ordinal) for ordinal, item in enumerate(ordered, 1))
    entry_count = len(entries)
    accepted_count = sum(item.accepted for item in entries)
    ready_count = sum(item.state == "ready" for item in entries)
    blocked_count = sum(item.state == "blocked" for item in entries)
    state = _state(entries)
    accepted = not entries or accepted_count == entry_count
    summary_body = {"registry_id": registry_id, "entry_count": entry_count, "accepted_count": accepted_count, "ready_count": ready_count, "blocked_count": blocked_count, "state": state, "accepted": accepted, "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary(**summary_body)
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    entries_address = address_entries(entries)
    manifest_body = {"registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifact_addresses": (entries_address, summary.content_address), "content_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest(**manifest_body)
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {"registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": entry_count, "accepted_count": accepted_count, "ready_count": ready_count, "blocked_count": blocked_count, "state": state, "accepted": accepted, "manifest": manifest, "summary": summary, "entries": entries}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry(**body, content_address=REGISTRY_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry(**body, content_address=address_registry(provisional))


def verify_registry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry):
        raise ValidationError("runtime registry verification requires a typed registry")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry.from_mapping(value.to_dict())


def registry_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry.from_mapping(value)


def registry_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry) -> str:
    return canonical_json(verify_registry(value).to_dict())


def registry_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry) -> str:
    value = verify_registry(value)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("field", "value"))
    for field in ("registry_id", "version", "boundary", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "content_address"):
        writer.writerow((field, json.dumps(getattr(value, field), ensure_ascii=False, sort_keys=True)))
    return output.getvalue()


def render_registry_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry) -> str:
    value = verify_registry(value)
    lines = ["# History-Diff Archive Transfer Recovery Execution Runtime Registry", "", f"- Registry: `{value.registry_id}`", f"- State: `{value.state}`", f"- Entries: `{value.entry_count}`", f"- Accepted: `{value.accepted_count}/{value.entry_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | runtime | state | accepted | execution | address |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.runtime_id}` | `{item.state}` | `{item.accepted}` | `{item.execution_id}` | `{item.runtime_address}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def entries_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntries) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntries.from_mapping(value.to_dict()).to_dict())


def summary_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary.from_mapping(value.to_dict()).to_dict())


def manifest_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest.from_mapping(value.to_dict()).to_dict())


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_registry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_registry(value)
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("runtime registry destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".history-diff-recovery-execution-runtime-registry-", dir=str(destination.parent)))
    try:
        entries = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntries(value.entries, address_entries(value.entries))
        documents = {"manifest.json": value.manifest.to_dict(), "registry.json": value.to_dict(), "entries.json": entries.to_dict(), "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("runtime registry destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("runtime registry artifact is not valid JSON") from error
    return _mapping(value, "runtime registry artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError("runtime registry artifact cannot be read") from error
    if actual != canonical_json(value):
        raise ValidationError("runtime registry artifact is not canonical")


def load_registry(destination: str | Path) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry:
    destination = Path(destination)
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("runtime registry source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)):
        raise ValidationError("runtime registry directory must contain the exact file set")
    if any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("runtime registry directory may contain only regular files")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        _read_canonical(destination / name, document)
        if len(canonical_json(document).encode("utf-8")) > MAX_REGISTRY_BYTES:
            raise ValidationError("runtime registry artifact exceeds its size bound")
    value = registry_from_mapping(documents["registry.json"])
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest.from_mapping(documents["manifest.json"])
    entries = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntries.from_mapping(documents["entries.json"])
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary.from_mapping(documents["summary.json"])
    if manifest.to_dict() != value.manifest.to_dict() or tuple(item.to_dict() for item in entries.entries) != tuple(item.to_dict() for item in value.entries) or entries.content_address != address_entries(value.entries) or summary.to_dict() != value.summary.to_dict():
        raise ValidationError("runtime registry component documents do not replay registry.json")
    if tuple(manifest.artifact_addresses) != (entries.content_address, summary.content_address):
        raise ValidationError("runtime registry manifest artifact addresses do not replay")
    return value


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": ["integer", "string", "boolean"]} for field in ENTRY_FIELDS}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "items": entry_schema()}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"registry_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}, "artifact_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"registry_id": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "ready_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def registry_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {"registry_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "ready_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "manifest": manifest_schema(), "summary": summary_schema(), "entries": {"type": "array", "items": entry_schema()}, "content_address": {"type": "string"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry", "type": "object", "additionalProperties": False, "required": list(REGISTRY_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "registry_prefix": REGISTRY_PREFIX, "entry_prefix": ENTRY_PREFIX, "entries_prefix": ENTRIES_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "summary_prefix": SUMMARY_PREFIX, "files": FILES, "states": STATES, "max_entries": MAX_ENTRIES, "operations": ("build_registry", "verify_registry", "registry_from_mapping", "persist_registry", "load_registry", "registry_json", "registry_csv", "render_registry_markdown", "entries_json", "summary_json", "manifest_json"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "REGISTRY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_REGISTRY_ID", "FILES", "ARTIFACT_FILES", "MANIFEST_ARTIFACT_FILES", "MAX_ENTRIES", "MAX_REGISTRY_BYTES", "STATES", "ENTRY_FIELDS", "ENTRIES_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "REGISTRY_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntry", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryEntries", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryManifest", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistrySummary", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry", "address_entry", "address_entries", "address_manifest", "address_summary", "address_registry", "entry_from_runtime", "build_registry", "verify_registry", "registry_from_mapping", "registry_json", "registry_csv", "render_registry_markdown", "entries_json", "summary_json", "manifest_json", "persist_registry", "load_registry", "entry_schema", "entries_schema", "manifest_schema", "summary_schema", "registry_schema", "capabilities"]
