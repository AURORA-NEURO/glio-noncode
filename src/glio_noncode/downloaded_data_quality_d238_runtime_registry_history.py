"""Append-only history for runtime admission registries."""

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

from . import downloaded_data_quality_d237_runtime_registry as registry_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = registry_model.VERSION + "-history-v1"
BOUNDARY = registry_model.BOUNDARY + "_history"
HISTORY_PREFIX = registry_model.REGISTRY_PREFIX + "-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
ENTRIES_PREFIX = HISTORY_PREFIX + "-entries"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
SUMMARY_PREFIX = HISTORY_PREFIX + "-summary"
DEFAULT_HISTORY_ID = HISTORY_PREFIX
FILES = ("manifest.json", "history.json", "entries.json", "summary.json")
ARTIFACT_FILES = ("entries.json", "summary.json")
STATES = registry_model.STATES
TRANSITIONS = ("initial", "improved", "regressed", "unchanged", "changed")
MAX_ENTRIES = 128
MAX_HISTORY_BYTES = 32 * 1024 * 1024
ENTRY_FIELDS = ("ordinal", "snapshot_id", "registry_id", "registry_address", "state", "release_ready", "entry_count", "ready_count", "blocked_count", "transition", "previous_address", "content_address")
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("history_id", "registry_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("history_id", "registry_id", "entry_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "latest_state", "latest_release_ready", "accepted", "content_address")
HISTORY_FIELDS = ("history_id", "registry_id", "version", "boundary", "entries", "entry_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "latest_state", "latest_release_ready", "accepted", "manifest", "summary", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if not value:
        return value
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
    return registry_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class RegistryHistoryEntry:
    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, snapshot_id: str, registry_id: str, registry_address: str, state: str, release_ready: bool, entry_count: int, ready_count: int, blocked_count: int, transition: str, previous_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history entry ordinal", MAX_ENTRIES, lower=1)
        self.snapshot_id = _label(snapshot_id, "runtime registry history snapshot ID")
        self.registry_id = _label(registry_id, "runtime registry history registry ID")
        self.registry_address = _address(registry_address, "runtime registry history registry address", registry_model.REGISTRY_PREFIX)
        if state not in STATES:
            raise ValidationError("runtime registry history entry state is unsupported")
        self.state = state
        self.release_ready = _bool(release_ready, "runtime registry history entry readiness")
        if self.release_ready != (self.state == "ready"):
            raise ValidationError("runtime registry history entry state and readiness disagree")
        self.entry_count = _count(entry_count, "runtime registry history entry registry count", registry_model.MAX_ENTRIES)
        self.ready_count = _count(ready_count, "runtime registry history entry ready count", registry_model.MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "runtime registry history entry blocked count", registry_model.MAX_ENTRIES)
        if self.ready_count + self.blocked_count != self.entry_count:
            raise ValidationError("runtime registry history entry counters do not conserve entries")
        if transition not in TRANSITIONS:
            raise ValidationError("runtime registry history transition is unsupported")
        self.transition = transition
        self.previous_address = _address(previous_address, "runtime registry history previous address", ENTRY_PREFIX, required=False)
        self.content_address = _address(content_address, "runtime registry history entry address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.ordinal == 1 and self.previous_address:
            raise ValidationError("initial runtime registry history entry cannot have a predecessor")
        if self.ordinal > 1 and not self.previous_address:
            raise ValidationError("non-initial runtime registry history entry requires a predecessor")
        if self.ordinal == 1 and self.transition != "initial":
            raise ValidationError("first runtime registry history entry must be initial")
        if self.ordinal > 1 and self.transition == "initial":
            raise ValidationError("only the first runtime registry history entry may be initial")
        if not self.content_address.startswith("pending:") and _address_for(self, ENTRY_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history entry address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryHistoryEntry":
        value = _mapping(value, "runtime registry history entry")
        _strict(value, set(cls.FIELDS), "runtime registry history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: RegistryHistoryEntry) -> str:
    if not isinstance(value, RegistryHistoryEntry):
        raise ValidationError("runtime registry history entry address requires a typed entry")
    return _address_for(value, ENTRY_PREFIX)


def _transition(previous: RegistryHistoryEntry | None, registry: registry_model.RuntimeRegistry) -> str:
    if previous is None:
        return "initial"
    old = (previous.state, previous.release_ready, previous.entry_count, previous.ready_count, previous.blocked_count)
    new = (registry.state, registry.release_ready, registry.entry_count, registry.ready_count, registry.blocked_count)
    if old == new:
        return "unchanged"
    if previous.state != "ready" and registry.state == "ready":
        return "improved"
    if previous.state == "ready" and registry.state != "ready":
        return "regressed"
    return "changed"


def _entry_for(registry: registry_model.RuntimeRegistry, ordinal: int, snapshot_id: str, previous: RegistryHistoryEntry | None) -> RegistryHistoryEntry:
    registry_model.verify_registry(registry)
    body = {"ordinal": ordinal, "snapshot_id": snapshot_id, "registry_id": registry.registry_id, "registry_address": registry.content_address, "state": registry.state, "release_ready": registry.release_ready, "entry_count": registry.entry_count, "ready_count": registry.ready_count, "blocked_count": registry.blocked_count, "transition": _transition(previous, registry), "previous_address": previous.content_address if previous else "", "content_address": f"pending:{ENTRY_PREFIX}"}
    provisional = RegistryHistoryEntry(**body)
    return RegistryHistoryEntry(**(body | {"content_address": address_entry(provisional)}))


class RegistryHistoryEntries:
    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[RegistryHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, RegistryHistoryEntry) else RegistryHistoryEntry.from_mapping(_mapping(item, "runtime registry history entry")) for item in _sequence(entries, "runtime registry history entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "runtime registry history entries address", ENTRIES_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("runtime registry history entry ordinals are not contiguous")
        if any(item.content_address != address_entry(item) for item in self.entries):
            raise ValidationError("runtime registry history entry addresses do not replay")
        if not self.content_address.startswith("pending:") and address_entries(self.entries) != self.content_address:
            raise ValidationError("runtime registry history entries address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history entries cross the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryHistoryEntries":
        value = _mapping(value, "runtime registry history entries")
        _strict(value, set(cls.FIELDS), "runtime registry history entries")
        return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[RegistryHistoryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, RegistryHistoryEntry) for item in typed):
        raise ValidationError("runtime registry history entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class RegistryHistoryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, history_id: str, registry_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.history_id = _label(history_id, "runtime registry history manifest history ID")
        self.registry_id = _label(registry_id, "runtime registry history manifest registry ID")
        self.version = _text(version, "runtime registry history manifest version", 1024)
        self.boundary = _text(boundary, "runtime registry history manifest boundary", 2048)
        self.files = tuple(_text(item, "runtime registry history manifest file", 128) for item in _sequence(files, "runtime registry history manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "runtime registry history manifest artifact address") for item in _sequence(artifact_addresses, "runtime registry history manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "runtime registry history manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime registry history manifest is not canonical")
        if not self.content_address.startswith("pending:") and address_manifest(self) != self.content_address:
            raise ValidationError("runtime registry history manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryHistoryManifest":
        value = _mapping(value, "runtime registry history manifest")
        _strict(value, set(cls.FIELDS), "runtime registry history manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: RegistryHistoryManifest) -> str:
    if not isinstance(value, RegistryHistoryManifest):
        raise ValidationError("runtime registry history manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class RegistryHistorySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, history_id: str, registry_id: str, entry_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_state: str, latest_release_ready: bool, accepted: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "runtime registry history summary history ID")
        self.registry_id = _label(registry_id, "runtime registry history summary registry ID")
        self.entry_count = _count(entry_count, "runtime registry history summary entry count", MAX_ENTRIES)
        self.initial_count = _count(initial_count, "runtime registry history summary initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "runtime registry history summary improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "runtime registry history summary regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "runtime registry history summary unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "runtime registry history summary changed count", MAX_ENTRIES)
        if latest_state not in STATES:
            raise ValidationError("runtime registry history latest state is unsupported")
        self.latest_state = latest_state
        self.latest_release_ready = _bool(latest_release_ready, "runtime registry history latest readiness")
        self.accepted = _bool(accepted, "runtime registry history acceptance")
        self.content_address = _address(content_address, "runtime registry history summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if sum((self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count)) != self.entry_count:
            raise ValidationError("runtime registry history transition counters do not conserve entries")
        if self.entry_count == 0 or self.initial_count != 1:
            raise ValidationError("runtime registry history requires one initial entry")
        if not self.content_address.startswith("pending:") and address_summary(self) != self.content_address:
            raise ValidationError("runtime registry history summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryHistorySummary":
        value = _mapping(value, "runtime registry history summary")
        _strict(value, set(cls.FIELDS), "runtime registry history summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: RegistryHistorySummary) -> str:
    if not isinstance(value, RegistryHistorySummary):
        raise ValidationError("runtime registry history summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class RegistryHistory:
    FIELDS = HISTORY_FIELDS

    def __init__(self, history_id: str, registry_id: str, version: str, boundary: str, entries: Sequence[RegistryHistoryEntry | Mapping[str, Any]], entry_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_state: str, latest_release_ready: bool, accepted: bool, manifest: Mapping[str, Any] | RegistryHistoryManifest, summary: Mapping[str, Any] | RegistryHistorySummary, content_address: str) -> None:
        self.history_id = _label(history_id, "runtime registry history ID")
        self.registry_id = _label(registry_id, "runtime registry history registry ID")
        self.version = _text(version, "runtime registry history version", 1024)
        self.boundary = _text(boundary, "runtime registry history boundary", 2048)
        self.entries = tuple(item if isinstance(item, RegistryHistoryEntry) else RegistryHistoryEntry.from_mapping(_mapping(item, "runtime registry history entry")) for item in _sequence(entries, "runtime registry history entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "runtime registry history entry count", MAX_ENTRIES)
        self.initial_count = _count(initial_count, "runtime registry history initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "runtime registry history improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "runtime registry history regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "runtime registry history unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "runtime registry history changed count", MAX_ENTRIES)
        if latest_state not in STATES:
            raise ValidationError("runtime registry history state is unsupported")
        self.latest_state = latest_state
        self.latest_release_ready = _bool(latest_release_ready, "runtime registry history readiness")
        self.accepted = _bool(accepted, "runtime registry history acceptance")
        self.manifest = manifest if isinstance(manifest, RegistryHistoryManifest) else RegistryHistoryManifest.from_mapping(_mapping(manifest, "runtime registry history manifest"))
        self.summary = summary if isinstance(summary, RegistryHistorySummary) else RegistryHistorySummary.from_mapping(_mapping(summary, "runtime registry history summary"))
        self.content_address = _address(content_address, "runtime registry history address", HISTORY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.entry_count != len(self.entries) or self.entry_count == 0:
            raise ValidationError("runtime registry history identity or count does not replay")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)) or any(item.registry_id != self.registry_id for item in self.entries):
            raise ValidationError("runtime registry history entry identity or order does not replay")
        if any(item.content_address != address_entry(item) for item in self.entries):
            raise ValidationError("runtime registry history entry addresses do not replay")
        if not all((not item.previous_address if item.ordinal == 1 else item.previous_address == self.entries[item.ordinal - 2].content_address) for item in self.entries):
            raise ValidationError("runtime registry history predecessor links do not replay")
        counts = tuple(sum(item.transition == transition for item in self.entries) for transition in TRANSITIONS)
        if counts != (self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count):
            raise ValidationError("runtime registry history transition counts do not replay")
        if (self.latest_state, self.latest_release_ready) != (self.entries[-1].state, self.entries[-1].release_ready):
            raise ValidationError("runtime registry history latest projection does not replay")
        expected_summary = (self.history_id, self.registry_id, self.entry_count, self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count, self.latest_state, self.latest_release_ready, self.accepted)
        actual_summary = tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1])
        if actual_summary != expected_summary or self.summary.content_address != address_summary(self.summary):
            raise ValidationError("runtime registry history summary does not replay")
        expected_manifest = (self.history_id, self.registry_id, VERSION, BOUNDARY, FILES, (address_entries(self.entries), self.summary.content_address))
        actual_manifest = (self.manifest.history_id, self.manifest.registry_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest):
            raise ValidationError("runtime registry history manifest does not replay")
        if not self.content_address.startswith("pending:") and address_history(self) != self.content_address:
            raise ValidationError("runtime registry history address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entries": [item.to_dict() for item in self.entries], "entry_count": self.entry_count, "initial_count": self.initial_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "latest_state": self.latest_state, "latest_release_ready": self.latest_release_ready, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryHistory":
        value = _mapping(value, "runtime registry history")
        _strict(value, set(cls.FIELDS), "runtime registry history")
        return cls(*(value[field] for field in cls.FIELDS))


def address_history(value: RegistryHistory) -> str:
    if not isinstance(value, RegistryHistory):
        raise ValidationError("runtime registry history address requires a typed history")
    return _address_for(value, HISTORY_PREFIX)


def _assemble(history_id: str, registry_id: str, entries: Sequence[RegistryHistoryEntry]) -> RegistryHistory:
    entries = tuple(entries)
    if not entries:
        raise ValidationError("runtime registry history requires at least one entry")
    summary = _seal(RegistryHistorySummary(history_id, registry_id, len(entries), *(sum(item.transition == transition for item in entries) for transition in TRANSITIONS), entries[-1].state, entries[-1].release_ready, True, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(RegistryHistoryManifest(history_id, registry_id, VERSION, BOUNDARY, FILES, (address_entries(entries), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(RegistryHistory(history_id, registry_id, VERSION, BOUNDARY, entries, len(entries), *(sum(item.transition == transition for item in entries) for transition in TRANSITIONS), entries[-1].state, entries[-1].release_ready, True, manifest, summary, f"pending:{HISTORY_PREFIX}"), address_history)


def build_history(registry: registry_model.RuntimeRegistry, *, history_id: str = DEFAULT_HISTORY_ID, snapshot_id: str = "initial") -> RegistryHistory:
    registry_model.verify_registry(registry)
    history_id = _label(history_id, "runtime registry history ID")
    snapshot_id = _label(snapshot_id, "runtime registry history snapshot ID")
    return _assemble(history_id, registry.registry_id, (_entry_for(registry, 1, snapshot_id, None),))


def append_history(history: RegistryHistory, registry: registry_model.RuntimeRegistry, *, snapshot_id: str | None = None, expected_head: str | None = None) -> RegistryHistory:
    if not isinstance(history, RegistryHistory):
        raise ValidationError("runtime registry history append requires a typed history")
    registry_model.verify_registry(registry)
    verify_history(history)
    if registry.registry_id != history.registry_id:
        raise ValidationError("runtime registry history append registry identity does not match")
    if expected_head is not None and expected_head != history.entries[-1].content_address:
        raise ValidationError("runtime registry history append head is stale")
    if registry.content_address in {item.registry_address for item in history.entries}:
        raise ValidationError("runtime registry history rejects duplicate registry address")
    snapshot_id = _label(snapshot_id or f"snapshot-{history.entry_count + 1}", "runtime registry history snapshot ID")
    if snapshot_id in {item.snapshot_id for item in history.entries}:
        raise ValidationError("runtime registry history rejects duplicate snapshot ID")
    if history.entry_count >= MAX_ENTRIES:
        raise ValidationError("runtime registry history reached its entry bound")
    return _assemble(history.history_id, history.registry_id, history.entries + (_entry_for(registry, history.entry_count + 1, snapshot_id, history.entries[-1]),))


def verify_history(value: RegistryHistory) -> RegistryHistory:
    if not isinstance(value, RegistryHistory):
        raise ValidationError("runtime registry history verification requires a typed history")
    value._validate()
    return value


def history_from_mapping(value: Mapping[str, Any]) -> RegistryHistory:
    return RegistryHistory.from_mapping(value)


def history_json(value: RegistryHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def entries_json(value: RegistryHistory) -> str:
    value = verify_history(value)
    return canonical_json({"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)})


def manifest_json(value: RegistryHistory) -> str:
    return canonical_json(verify_history(value).manifest.to_dict())


def summary_json(value: RegistryHistory) -> str:
    return canonical_json(verify_history(value).summary.to_dict())


def history_csv(value: RegistryHistory) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ENTRY_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_history(value).entries)
    return output.getvalue()


def render_history_markdown(value: RegistryHistory) -> str:
    value = verify_history(value)
    lines = [f"# Runtime registry history {value.history_id}", "", f"- Registry: {value.registry_id}", f"- Latest state: {value.latest_state}", f"- Latest ready: {str(value.latest_release_ready).lower()}", f"- Entries: {value.entry_count}", f"- Improved: {value.improved_count}", f"- Regressed: {value.regressed_count}", "", "| Snapshot | Transition | State | Ready | Registry entries |", "| --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {item.snapshot_id} | {item.transition} | {item.state} | {str(item.release_ready).lower()} | {item.entry_count} |" for item in value.entries)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_history(value: RegistryHistory, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_history(value)
    destination = Path(destination)
    _validate_parent(destination.parent, "runtime registry history destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("runtime registry history destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-runtime-registry-history-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "history.json": value.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "summary.json": value.summary.to_dict()}
    try:
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
        value = _strict_json_loads(read_text(path, field="runtime registry history artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("runtime registry history artifact is not valid JSON") from error
    return _mapping(value, "runtime registry history artifact")


def load_history(destination: str | Path) -> RegistryHistory:
    destination = Path(destination)
    _validate_parent(destination.parent, "runtime registry history input")
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("runtime registry history source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("runtime registry history directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="runtime registry history artifact") != serialized or len(serialized.encode("utf-8")) > MAX_HISTORY_BYTES:
            raise ValidationError("runtime registry history artifact is non-canonical or exceeds its size bound")
    value = history_from_mapping(documents["history.json"])
    expected = {"manifest.json": value.manifest.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()):
        raise ValidationError("runtime registry history component documents do not replay history.json")
    return verify_history(value)


def run_history(registry: registry_model.RuntimeRegistry, *, history_id: str = DEFAULT_HISTORY_ID, snapshot_id: str = "initial", destination: str | Path | None = None, overwrite: bool = False) -> RegistryHistory:
    value = build_history(registry, history_id=history_id, snapshot_id=snapshot_id)
    if destination is not None:
        persist_history(value, destination, overwrite=overwrite)
    return value


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistoryEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "integer" if field in ("ordinal", "entry_count", "ready_count", "blocked_count") else "boolean" if field == "release_ready" else "string"} for field in ENTRY_FIELDS}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistoryEntries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "items": {"$ref": "#/$defs/entry"}}, "content_address": {"type": "string"}}, "$defs": {"entry": entry_schema()}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistoryManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistorySummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("latest_release_ready", "accepted") else "string"} for field in SUMMARY_FIELDS}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistory", "type": "object", "additionalProperties": False, "required": list(HISTORY_FIELDS), "properties": {field: {"type": "array" if field == "entries" else "object" if field in ("manifest", "summary") else "integer" if field.endswith("count") else "boolean" if field in ("latest_release_ready", "accepted") else "string"} for field in HISTORY_FIELDS}, "$defs": {"entry": entry_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "states": STATES, "transitions": TRANSITIONS, "max_entries": MAX_ENTRIES, "features": ("append-only registry snapshots", "stable registry identity", "optimistic expected-head appends", "duplicate snapshot and address rejection", "deterministic transitions", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "HISTORY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_HISTORY_ID", "FILES", "ARTIFACT_FILES", "STATES", "TRANSITIONS", "MAX_ENTRIES", "MAX_HISTORY_BYTES", "ENTRY_FIELDS", "ENTRIES_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "HISTORY_FIELDS", "RegistryHistoryEntry", "RegistryHistoryEntries", "RegistryHistoryManifest", "RegistryHistorySummary", "RegistryHistory", "address_entry", "address_entries", "address_manifest", "address_summary", "address_history", "build_history", "append_history", "verify_history", "history_from_mapping", "history_json", "entries_json", "manifest_json", "summary_json", "history_csv", "render_history_markdown", "persist_history", "load_history", "run_history", "entry_schema", "entries_schema", "manifest_schema", "summary_schema", "history_schema", "capabilities"]













