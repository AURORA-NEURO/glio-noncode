"""Deterministic admission registry for runtime registry history diff policy runtimes."""
from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_quality_d312_history_diff_runtime as runtime_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = runtime_model.VERSION + "-registry-v1"
BOUNDARY = runtime_model.BOUNDARY + "_registry"
# Keep the D313 address namespace compact. The upstream versioned runtime
# namespace remains in each typed runtime address, but concatenating every
# historical layer into query IDs eventually exceeds the public label bound.
REGISTRY_PREFIX = "glio-noncode-d313-runtime-registry"
ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
ENTRIES_PREFIX = REGISTRY_PREFIX + "-entries"
MANIFEST_PREFIX = REGISTRY_PREFIX + "-manifest"
SUMMARY_PREFIX = REGISTRY_PREFIX + "-summary"
DEFAULT_REGISTRY_ID = REGISTRY_PREFIX
FILES = ("manifest.json", "registry.json", "entries.json", "summary.json")
ARTIFACT_FILES = ("entries.json", "summary.json")
STATES = ("empty", "ready", "blocked")
MAX_ENTRIES = 128
MAX_REGISTRY_BYTES = 32 * 1024 * 1024
ENTRY_FIELDS = ("ordinal", "runtime_id", "runtime_address", "diff_id", "diff_address", "state", "release_ready", "check_count", "passed_count", "item_count", "content_address")
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("registry_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("registry_id", "entry_count", "ready_count", "blocked_count", "accepted", "release_ready", "state", "content_address")
REGISTRY_FIELDS = ("registry_id", "version", "boundary", "entry_count", "ready_count", "blocked_count", "accepted", "release_ready", "state", "manifest", "summary", "entries", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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
    return runtime_model.diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class RuntimeRegistryEntry:
    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, runtime_id: str, runtime_address: str, diff_id: str, diff_address: str, state: str, release_ready: bool, check_count: int, passed_count: int, item_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff runtime registry entry ordinal", MAX_ENTRIES, lower=1)
        self.runtime_id = _label(runtime_id, "diff runtime registry runtime ID")
        self.runtime_address = _address(runtime_address, "diff runtime registry runtime address", runtime_model.RUNTIME_PREFIX)
        self.diff_id = _label(diff_id, "diff runtime registry diff ID")
        self.diff_address = _address(diff_address, "diff runtime registry diff address", runtime_model.diff_model.DIFF_PREFIX)
        if state not in STATES[1:]:
            raise ValidationError("diff runtime registry entry state is unsupported")
        self.state = state
        self.release_ready = _bool(release_ready, "diff runtime registry entry readiness")
        if self.release_ready != (self.state == "ready"):
            raise ValidationError("diff runtime registry entry state and readiness disagree")
        self.check_count = _count(check_count, "diff runtime registry entry check count", runtime_model.MAX_CHECKS)
        self.passed_count = _count(passed_count, "diff runtime registry entry passed count", runtime_model.MAX_CHECKS)
        self.item_count = _count(item_count, "diff runtime registry entry item count", runtime_model.diff_model.MAX_ITEMS)
        if self.passed_count > self.check_count:
            raise ValidationError("diff runtime registry entry passed count exceeds check count")
        self.content_address = _address(content_address, "diff runtime registry entry address", ENTRY_PREFIX); self._validate()

    def _validate(self) -> None:
        if not self.content_address.startswith("pending:") and _address_for(self, ENTRY_PREFIX) != self.content_address:
            raise ValidationError("diff runtime registry entry address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff runtime registry entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeRegistryEntry":
        value = _mapping(value, "diff runtime registry entry"); _strict(value, set(cls.FIELDS), "diff runtime registry entry"); return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: RuntimeRegistryEntry) -> str:
    if not isinstance(value, RuntimeRegistryEntry):
        raise ValidationError("diff runtime registry entry address requires a typed entry")
    return _address_for(value, ENTRY_PREFIX)


def entry_from_runtime(value: runtime_model.DiffRuntime, ordinal: int) -> RuntimeRegistryEntry:
    runtime_model.verify_runtime(value)
    body = {"ordinal": ordinal, "runtime_id": value.runtime_id, "runtime_address": value.content_address, "diff_id": value.diff_id, "diff_address": value.diff_address, "state": value.state, "release_ready": value.release_ready, "check_count": value.check_count, "passed_count": value.passed_count, "item_count": value.item_count, "content_address": f"pending:{ENTRY_PREFIX}"}
    provisional = RuntimeRegistryEntry(**body); return RuntimeRegistryEntry(**(body | {"content_address": address_entry(provisional)}))


class RuntimeRegistryEntries:
    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[RuntimeRegistryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, RuntimeRegistryEntry) else RuntimeRegistryEntry.from_mapping(_mapping(item, "diff runtime registry entry")) for item in _sequence(entries, "diff runtime registry entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "diff runtime registry entries address", ENTRIES_PREFIX); self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("diff runtime registry entry ordinals are not contiguous")
        if not self.content_address.startswith("pending:") and address_entries(self.entries) != self.content_address:
            raise ValidationError("diff runtime registry entries address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff runtime registry entries cross the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeRegistryEntries":
        value = _mapping(value, "diff runtime registry entries"); _strict(value, set(cls.FIELDS), "diff runtime registry entries"); return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[RuntimeRegistryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, RuntimeRegistryEntry) for item in typed):
        raise ValidationError("diff runtime registry entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class RuntimeRegistryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.registry_id = _label(registry_id, "diff runtime registry manifest registry ID")
        self.version = _text(version, "diff runtime registry manifest version", 1024)
        self.boundary = _text(boundary, "diff runtime registry manifest boundary", 2048)
        self.files = tuple(_text(item, "diff runtime registry manifest file", 128) for item in _sequence(files, "diff runtime registry manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "diff runtime registry manifest artifact address") for item in _sequence(artifact_addresses, "diff runtime registry manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "diff runtime registry manifest address", MANIFEST_PREFIX); self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("diff runtime registry manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("diff runtime registry manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff runtime registry manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeRegistryManifest":
        value = _mapping(value, "diff runtime registry manifest"); _strict(value, set(cls.FIELDS), "diff runtime registry manifest"); return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: RuntimeRegistryManifest) -> str:
    if not isinstance(value, RuntimeRegistryManifest):
        raise ValidationError("diff runtime registry manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class RuntimeRegistrySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, registry_id: str, entry_count: int, ready_count: int, blocked_count: int, accepted: bool, release_ready: bool, state: str, content_address: str) -> None:
        self.registry_id = _label(registry_id, "diff runtime registry summary registry ID")
        self.entry_count = _count(entry_count, "diff runtime registry summary entry count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "diff runtime registry summary ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "diff runtime registry summary blocked count", MAX_ENTRIES)
        self.accepted = _bool(accepted, "diff runtime registry summary acceptance")
        self.release_ready = _bool(release_ready, "diff runtime registry summary readiness")
        if state not in STATES:
            raise ValidationError("diff runtime registry summary state is unsupported")
        self.state = state; self.content_address = _address(content_address, "diff runtime registry summary address", SUMMARY_PREFIX); self._validate()

    def _validate(self) -> None:
        expected_state = "empty" if self.entry_count == 0 else "ready" if self.blocked_count == 0 else "blocked"
        if self.ready_count + self.blocked_count != self.entry_count or self.state != expected_state or self.accepted != (self.entry_count > 0) or self.release_ready != (self.state == "ready"):
            raise ValidationError("diff runtime registry summary disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("diff runtime registry summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff runtime registry summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeRegistrySummary":
        value = _mapping(value, "diff runtime registry summary"); _strict(value, set(cls.FIELDS), "diff runtime registry summary"); return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: RuntimeRegistrySummary) -> str:
    if not isinstance(value, RuntimeRegistrySummary):
        raise ValidationError("diff runtime registry summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class RuntimeRegistry:
    FIELDS = REGISTRY_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, entry_count: int, ready_count: int, blocked_count: int, accepted: bool, release_ready: bool, state: str, manifest: Mapping[str, Any] | RuntimeRegistryManifest, summary: Mapping[str, Any] | RuntimeRegistrySummary, entries: Sequence[RuntimeRegistryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.registry_id = _label(registry_id, "diff runtime registry ID"); self.version = _text(version, "diff runtime registry version", 1024); self.boundary = _text(boundary, "diff runtime registry boundary", 2048)
        self.entry_count = _count(entry_count, "diff runtime registry entry count", MAX_ENTRIES); self.ready_count = _count(ready_count, "diff runtime registry ready count", MAX_ENTRIES); self.blocked_count = _count(blocked_count, "diff runtime registry blocked count", MAX_ENTRIES)
        self.accepted = _bool(accepted, "diff runtime registry acceptance"); self.release_ready = _bool(release_ready, "diff runtime registry readiness")
        if state not in STATES: raise ValidationError("diff runtime registry state is unsupported")
        self.state = state; self.manifest = manifest if isinstance(manifest, RuntimeRegistryManifest) else RuntimeRegistryManifest.from_mapping(_mapping(manifest, "diff runtime registry manifest")); self.summary = summary if isinstance(summary, RuntimeRegistrySummary) else RuntimeRegistrySummary.from_mapping(_mapping(summary, "diff runtime registry summary")); self.entries = tuple(item if isinstance(item, RuntimeRegistryEntry) else RuntimeRegistryEntry.from_mapping(_mapping(item, "diff runtime registry entry")) for item in _sequence(entries, "diff runtime registry entries", MAX_ENTRIES)); self.content_address = _address(content_address, "diff runtime registry address", REGISTRY_PREFIX); self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.entry_count != len(self.entries) or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("diff runtime registry identity or entry count does not replay")
        if len({item.runtime_id for item in self.entries}) != self.entry_count or len({item.runtime_address for item in self.entries}) != self.entry_count:
            raise ValidationError("diff runtime registry contains duplicate runtime identity or address")
        ready = sum(item.state == "ready" for item in self.entries); blocked = sum(item.state == "blocked" for item in self.entries)
        if (self.ready_count, self.blocked_count) != (ready, blocked): raise ValidationError("diff runtime registry state counters do not replay")
        expected = (self.registry_id, self.entry_count, self.ready_count, self.blocked_count, self.accepted, self.release_ready, self.state)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected or self.summary.content_address != address_summary(self.summary): raise ValidationError("diff runtime registry summary does not replay")
        expected_manifest = (self.registry_id, VERSION, BOUNDARY, FILES, (address_entries(self.entries), self.summary.content_address)); actual_manifest = (self.manifest.registry_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest): raise ValidationError("diff runtime registry manifest does not replay")
        if not self.content_address.startswith("pending:") and address_registry(self) != self.content_address: raise ValidationError("diff runtime registry address does not replay")
        if not _public(self.to_dict()): raise ValidationError("diff runtime registry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeRegistry":
        value = _mapping(value, "diff runtime registry"); _strict(value, set(cls.FIELDS), "diff runtime registry"); return cls(*(value[field] for field in cls.FIELDS))


def address_registry(value: RuntimeRegistry) -> str:
    if not isinstance(value, RuntimeRegistry): raise ValidationError("diff runtime registry address requires a typed registry")
    return _address_for(value, REGISTRY_PREFIX)


def build_registry(runtimes: Sequence[runtime_model.DiffRuntime], *, registry_id: str = DEFAULT_REGISTRY_ID) -> RuntimeRegistry:
    typed = tuple(runtimes)
    if len(typed) > MAX_ENTRIES or any(not isinstance(item, runtime_model.DiffRuntime) for item in typed): raise ValidationError("diff runtime registry requires a bounded sequence of typed runtimes")
    for item in typed: runtime_model.verify_runtime(item)
    entries = tuple(entry_from_runtime(item, index) for index, item in enumerate(typed, 1)); entry_count = len(entries); ready_count = sum(item.state == "ready" for item in entries); blocked_count = sum(item.state == "blocked" for item in entries); accepted = entry_count > 0; release_ready = accepted and blocked_count == 0; state = "empty" if entry_count == 0 else "ready" if release_ready else "blocked"
    summary = _seal(RuntimeRegistrySummary(registry_id, entry_count, ready_count, blocked_count, accepted, release_ready, state, f"pending:{SUMMARY_PREFIX}"), address_summary); manifest = _seal(RuntimeRegistryManifest(registry_id, VERSION, BOUNDARY, FILES, (address_entries(entries), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(RuntimeRegistry(registry_id, VERSION, BOUNDARY, entry_count, ready_count, blocked_count, accepted, release_ready, state, manifest, summary, entries, f"pending:{REGISTRY_PREFIX}"), address_registry)


def verify_registry(value: RuntimeRegistry) -> RuntimeRegistry:
    if not isinstance(value, RuntimeRegistry): raise ValidationError("diff runtime registry verification requires a typed registry")
    value._validate(); return value


def registry_from_mapping(value: Mapping[str, Any]) -> RuntimeRegistry: return RuntimeRegistry.from_mapping(value)
def registry_json(value: RuntimeRegistry) -> str: return canonical_json(verify_registry(value).to_dict())
def entries_json(value: RuntimeRegistry) -> str:
    value = verify_registry(value); return canonical_json({"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)})
def manifest_json(value: RuntimeRegistry) -> str: return canonical_json(verify_registry(value).manifest.to_dict())
def summary_json(value: RuntimeRegistry) -> str: return canonical_json(verify_registry(value).summary.to_dict())


def registry_csv(value: RuntimeRegistry) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ENTRY_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_registry(value).entries); return output.getvalue()


def render_registry_markdown(value: RuntimeRegistry) -> str:
    value = verify_registry(value); lines = [f"# Diff runtime registry {value.registry_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Entries: {value.entry_count}", f"- Ready: {value.ready_count}", f"- Blocked: {value.blocked_count}", "", "| Runtime | State | Ready | Checks | Items |", "| --- | --- | --- | ---: | ---: |"]; lines.extend(f"| {item.runtime_id} | {item.state} | {str(item.release_ready).lower()} | {item.passed_count}/{item.check_count} | {item.item_count} |" for item in value.entries); return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None: path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_registry(value: RuntimeRegistry, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_registry(value); destination = Path(destination); _validate_parent(destination.parent, "diff runtime registry destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)): raise ValidationError("diff runtime registry destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True); temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-diff-runtime-registry-", dir=str(destination.parent))); documents = {"manifest.json": value.manifest.to_dict(), "registry.json": value.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES: _write(temporary / name, documents[name])
        if destination.exists(): shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True); raise ValidationError("diff runtime registry destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try: value = _strict_json_loads(read_text(path, field="diff runtime registry artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error: raise ValidationError("diff runtime registry artifact is not valid JSON") from error
    return _mapping(value, "diff runtime registry artifact")


def load_registry(destination: str | Path) -> RuntimeRegistry:
    destination = Path(destination); _validate_parent(destination.parent, "diff runtime registry input")
    if not destination.is_dir() or destination.is_symlink(): raise ValidationError("diff runtime registry source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children): raise ValidationError("diff runtime registry directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="diff runtime registry artifact") != serialized or len(serialized.encode("utf-8")) > MAX_REGISTRY_BYTES: raise ValidationError("diff runtime registry artifact is non-canonical or exceeds its size bound")
    value = registry_from_mapping(documents["registry.json"]); expected = {"manifest.json": value.manifest.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()): raise ValidationError("diff runtime registry component documents do not replay registry.json")
    return verify_registry(value)


def run_registry(runtimes: Sequence[runtime_model.DiffRuntime], *, registry_id: str = DEFAULT_REGISTRY_ID, destination: str | Path | None = None, overwrite: bool = False) -> RuntimeRegistry:
    value = build_registry(runtimes, registry_id=registry_id)
    if destination is not None: persist_registry(value, destination, overwrite=overwrite)
    return value


def entry_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistryEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "integer" if field in ("ordinal", "check_count", "passed_count", "item_count") else "boolean" if field == "release_ready" else "string"} for field in ENTRY_FIELDS}}
def entries_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistryEntries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "items": {"$ref": "#/$defs/entry"}}, "content_address": {"type": "string"}}, "$defs": {"entry": entry_schema()}}
def manifest_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistryManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}
def summary_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistrySummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("accepted", "release_ready") else "string"} for field in SUMMARY_FIELDS}}
def registry_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistry", "type": "object", "additionalProperties": False, "required": list(REGISTRY_FIELDS), "properties": {field: {"type": "array" if field == "entries" else "object" if field in ("manifest", "summary") else "integer" if field.endswith("count") else "boolean" if field in ("accepted", "release_ready") else "string"} for field in REGISTRY_FIELDS}, "$defs": {"entry": entry_schema()}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "states": STATES, "max_entries": MAX_ENTRIES, "features": ("multi-runtime diff admission", "duplicate runtime identity and address rejection", "ready and blocked aggregate folding", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "REGISTRY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_REGISTRY_ID", "FILES", "ARTIFACT_FILES", "STATES", "MAX_ENTRIES", "MAX_REGISTRY_BYTES", "ENTRY_FIELDS", "ENTRIES_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "REGISTRY_FIELDS", "RuntimeRegistryEntry", "RuntimeRegistryEntries", "RuntimeRegistryManifest", "RuntimeRegistrySummary", "RuntimeRegistry", "address_entry", "address_entries", "address_manifest", "address_summary", "address_registry", "entry_from_runtime", "build_registry", "verify_registry", "registry_from_mapping", "registry_json", "entries_json", "manifest_json", "summary_json", "registry_csv", "render_registry_markdown", "persist_registry", "load_registry", "run_registry", "entry_schema", "entries_schema", "manifest_schema", "summary_schema", "registry_schema", "capabilities"]





















