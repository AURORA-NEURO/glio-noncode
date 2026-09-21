"""Append-only history for D477 release-batch promotion decisions."""

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

from . import downloaded_data_quality_d477_release_batch as batch_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = batch_model.VERSION + "-history-v1"
BOUNDARY = batch_model.BOUNDARY + "_history"
HISTORY_PREFIX = batch_model.BATCH_PREFIX + "-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
ENTRIES_PREFIX = HISTORY_PREFIX + "-entries"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
SUMMARY_PREFIX = HISTORY_PREFIX + "-summary"
DEFAULT_HISTORY_ID = HISTORY_PREFIX
FILES = ("manifest.json", "history.json", "entries.json", "summary.json")
ARTIFACT_FILES = ("entries.json", "summary.json")
STATES = batch_model.STATES
TRANSITIONS = ("initial", "promoted", "regressed", "unchanged", "changed")
MAX_ENTRIES = 128
MAX_HISTORY_BYTES = 32 * 1024 * 1024
ENTRY_FIELDS = ("ordinal", "snapshot_id", "batch_id", "batch_address", "state", "release_ready", "item_count", "ready_count", "blocked_count", "transition", "previous_address", "content_address")
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("history_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("history_id", "entry_count", "initial_count", "promoted_count", "regressed_count", "unchanged_count", "changed_count", "latest_state", "latest_release_ready", "accepted", "content_address")
HISTORY_FIELDS = ("history_id", "version", "boundary", "entries", "entry_count", "initial_count", "promoted_count", "regressed_count", "unchanged_count", "changed_count", "latest_state", "latest_release_ready", "accepted", "manifest", "summary", "content_address")


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
    return batch_model.runtime_model.diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class BatchHistoryEntry:
    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, snapshot_id: str, batch_id: str, batch_address: str, state: str, release_ready: bool, item_count: int, ready_count: int, blocked_count: int, transition: str, previous_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release batch history entry ordinal", MAX_ENTRIES, lower=1)
        self.snapshot_id = _label(snapshot_id, "release batch history snapshot ID")
        self.batch_id = _label(batch_id, "release batch history batch ID")
        self.batch_address = _address(batch_address, "release batch history batch address", batch_model.BATCH_PREFIX)
        if state not in STATES:
            raise ValidationError("release batch history entry state is unsupported")
        self.state = state
        self.release_ready = _bool(release_ready, "release batch history entry readiness")
        self.item_count = _count(item_count, "release batch history entry item count", batch_model.MAX_ITEMS)
        self.ready_count = _count(ready_count, "release batch history entry ready count", batch_model.MAX_ITEMS)
        self.blocked_count = _count(blocked_count, "release batch history entry blocked count", batch_model.MAX_ITEMS)
        if transition not in TRANSITIONS:
            raise ValidationError("release batch history transition is unsupported")
        self.transition = transition
        self.previous_address = _address(previous_address, "release batch history previous address", ENTRY_PREFIX, required=False)
        self.content_address = _address(content_address, "release batch history entry address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.release_ready != (self.state == "ready") or self.ready_count + self.blocked_count != self.item_count or (self.transition == "initial") != (self.ordinal == 1) or (self.ordinal == 1 and self.previous_address) or (self.ordinal > 1 and not self.previous_address):
            raise ValidationError("release batch history entry disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, ENTRY_PREFIX) != self.content_address:
            raise ValidationError("release batch history entry address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchHistoryEntry":
        value = _mapping(value, "release batch history entry")
        _strict(value, set(cls.FIELDS), "release batch history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: BatchHistoryEntry) -> str:
    if not isinstance(value, BatchHistoryEntry):
        raise ValidationError("release batch history entry address requires a typed entry")
    return _address_for(value, ENTRY_PREFIX)


class BatchHistoryEntries:
    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[BatchHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, BatchHistoryEntry) else BatchHistoryEntry.from_mapping(_mapping(item, "release batch history entry")) for item in _sequence(entries, "release batch history entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "release batch history entries address", ENTRIES_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("release batch history entry ordinals are not contiguous")
        if not self.content_address.startswith("pending:") and address_entries(self.entries) != self.content_address:
            raise ValidationError("release batch history entries address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch history entries cross the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchHistoryEntries":
        value = _mapping(value, "release batch history entries")
        _strict(value, set(cls.FIELDS), "release batch history entries")
        return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[BatchHistoryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, BatchHistoryEntry) for item in typed):
        raise ValidationError("release batch history entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class BatchHistoryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, history_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.history_id = _label(history_id, "release batch history manifest history ID")
        self.version = _text(version, "release batch history manifest version", 1024)
        self.boundary = _text(boundary, "release batch history manifest boundary", 2048)
        self.files = tuple(_text(item, "release batch history manifest file", 128) for item in _sequence(files, "release batch history manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "release batch history manifest artifact address") for item in _sequence(artifact_addresses, "release batch history manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "release batch history manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release batch history manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("release batch history manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch history manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchHistoryManifest":
        value = _mapping(value, "release batch history manifest")
        _strict(value, set(cls.FIELDS), "release batch history manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: BatchHistoryManifest) -> str:
    if not isinstance(value, BatchHistoryManifest):
        raise ValidationError("release batch history manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class BatchHistorySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, history_id: str, entry_count: int, initial_count: int, promoted_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_state: str, latest_release_ready: bool, accepted: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "release batch history summary history ID")
        self.entry_count = _count(entry_count, "release batch history summary entry count", MAX_ENTRIES)
        self.initial_count = _count(initial_count, "release batch history summary initial count", MAX_ENTRIES)
        self.promoted_count = _count(promoted_count, "release batch history summary promoted count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "release batch history summary regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "release batch history summary unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "release batch history summary changed count", MAX_ENTRIES)
        if latest_state not in STATES:
            raise ValidationError("release batch history latest state is unsupported")
        self.latest_state = latest_state
        self.latest_release_ready = _bool(latest_release_ready, "release batch history latest readiness")
        self.accepted = _bool(accepted, "release batch history acceptance")
        self.content_address = _address(content_address, "release batch history summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.initial_count + self.promoted_count + self.regressed_count + self.unchanged_count + self.changed_count != self.entry_count or self.latest_release_ready != (self.latest_state == "ready") or self.accepted != (self.entry_count > 0):
            raise ValidationError("release batch history summary disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("release batch history summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch history summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchHistorySummary":
        value = _mapping(value, "release batch history summary")
        _strict(value, set(cls.FIELDS), "release batch history summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: BatchHistorySummary) -> str:
    if not isinstance(value, BatchHistorySummary):
        raise ValidationError("release batch history summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class ReleaseBatchHistory:
    FIELDS = HISTORY_FIELDS

    def __init__(self, history_id: str, version: str, boundary: str, entries: Sequence[BatchHistoryEntry | Mapping[str, Any]], entry_count: int, initial_count: int, promoted_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_state: str, latest_release_ready: bool, accepted: bool, manifest: Mapping[str, Any] | BatchHistoryManifest, summary: Mapping[str, Any] | BatchHistorySummary, content_address: str) -> None:
        self.history_id = _label(history_id, "release batch history ID")
        self.version = _text(version, "release batch history version", 1024)
        self.boundary = _text(boundary, "release batch history boundary", 2048)
        self.entries = tuple(item if isinstance(item, BatchHistoryEntry) else BatchHistoryEntry.from_mapping(_mapping(item, "release batch history entry")) for item in _sequence(entries, "release batch history entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "release batch history entry count", MAX_ENTRIES)
        self.initial_count = _count(initial_count, "release batch history initial count", MAX_ENTRIES)
        self.promoted_count = _count(promoted_count, "release batch history promoted count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "release batch history regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "release batch history unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "release batch history changed count", MAX_ENTRIES)
        if latest_state not in STATES:
            raise ValidationError("release batch history latest state is unsupported")
        self.latest_state = latest_state
        self.latest_release_ready = _bool(latest_release_ready, "release batch history latest readiness")
        self.accepted = _bool(accepted, "release batch history acceptance")
        self.manifest = manifest if isinstance(manifest, BatchHistoryManifest) else BatchHistoryManifest.from_mapping(_mapping(manifest, "release batch history manifest"))
        self.summary = summary if isinstance(summary, BatchHistorySummary) else BatchHistorySummary.from_mapping(_mapping(summary, "release batch history summary"))
        self.content_address = _address(content_address, "release batch history address", HISTORY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.entry_count != len(self.entries) or self.entry_count > MAX_ENTRIES:
            raise ValidationError("release batch history identity or entry count does not replay")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)) or len({item.snapshot_id for item in self.entries}) != self.entry_count or len({item.batch_address for item in self.entries}) != self.entry_count:
            raise ValidationError("release batch history entries are not unique and contiguous")
        counts = tuple(sum(item.transition == transition for item in self.entries) for transition in ("initial", "promoted", "regressed", "unchanged", "changed"))
        if (self.initial_count, self.promoted_count, self.regressed_count, self.unchanged_count, self.changed_count) != counts:
            raise ValidationError("release batch history transition counters do not replay")
        latest = self.entries[-1] if self.entries else None
        if latest is None and (self.latest_state != "empty" or self.latest_release_ready or self.accepted):
            raise ValidationError("empty release batch history disposition does not replay")
        if latest is not None and (self.latest_state, self.latest_release_ready, self.accepted) != (latest.state, latest.release_ready, True):
            raise ValidationError("release batch history latest disposition does not replay")
        expected_summary = (self.history_id, self.entry_count, self.initial_count, self.promoted_count, self.regressed_count, self.unchanged_count, self.changed_count, self.latest_state, self.latest_release_ready, self.accepted)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected_summary or self.summary.content_address != address_summary(self.summary):
            raise ValidationError("release batch history summary does not replay")
        expected_manifest = (self.history_id, VERSION, BOUNDARY, FILES, (address_entries(self.entries), self.summary.content_address))
        actual_manifest = (self.manifest.history_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest):
            raise ValidationError("release batch history manifest does not replay")
        if not self.content_address.startswith("pending:") and address_history(self) != self.content_address:
            raise ValidationError("release batch history address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch history crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "version": self.version, "boundary": self.boundary, "entries": [item.to_dict() for item in self.entries], "entry_count": self.entry_count, "initial_count": self.initial_count, "promoted_count": self.promoted_count, "regressed_count": self.regressed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "latest_state": self.latest_state, "latest_release_ready": self.latest_release_ready, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReleaseBatchHistory":
        value = _mapping(value, "release batch history")
        _strict(value, set(cls.FIELDS), "release batch history")
        return cls(*(value[field] for field in cls.FIELDS))


def address_history(value: ReleaseBatchHistory) -> str:
    if not isinstance(value, ReleaseBatchHistory):
        raise ValidationError("release batch history address requires a typed history")
    return _address_for(value, HISTORY_PREFIX)


def _entry(batch: batch_model.ReleaseBatch, ordinal: int, snapshot_id: str, transition: str, previous_address: str) -> BatchHistoryEntry:
    batch_model.verify_batch(batch)
    body = {"ordinal": ordinal, "snapshot_id": snapshot_id, "batch_id": batch.batch_id, "batch_address": batch.content_address, "state": batch.state, "release_ready": batch.release_ready, "item_count": batch.item_count, "ready_count": batch.ready_count, "blocked_count": batch.blocked_count, "transition": transition, "previous_address": previous_address, "content_address": f"pending:{ENTRY_PREFIX}"}
    provisional = BatchHistoryEntry(**body)
    return BatchHistoryEntry(**(body | {"content_address": address_entry(provisional)}))


def _history(history_id: str, entries: Sequence[BatchHistoryEntry]) -> ReleaseBatchHistory:
    typed = tuple(entries)
    initial_count, promoted_count, regressed_count, unchanged_count, changed_count = (sum(item.transition == transition for item in typed) for transition in ("initial", "promoted", "regressed", "unchanged", "changed"))
    latest = typed[-1] if typed else None
    latest_state = latest.state if latest is not None else "empty"
    latest_ready = latest.release_ready if latest is not None else False
    accepted = bool(typed)
    summary = _seal(BatchHistorySummary(history_id, len(typed), initial_count, promoted_count, regressed_count, unchanged_count, changed_count, latest_state, latest_ready, accepted, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(BatchHistoryManifest(history_id, VERSION, BOUNDARY, FILES, (address_entries(typed), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(ReleaseBatchHistory(history_id, VERSION, BOUNDARY, typed, len(typed), initial_count, promoted_count, regressed_count, unchanged_count, changed_count, latest_state, latest_ready, accepted, manifest, summary, f"pending:{HISTORY_PREFIX}"), address_history)


def build_history(batch: batch_model.ReleaseBatch, *, history_id: str = DEFAULT_HISTORY_ID, snapshot_id: str = "initial") -> ReleaseBatchHistory:
    if not isinstance(batch, batch_model.ReleaseBatch):
        raise ValidationError("release batch history requires a typed batch")
    return _history(history_id, (_entry(batch, 1, snapshot_id, "initial", ""),))


def append_history(history: ReleaseBatchHistory, batch: batch_model.ReleaseBatch, *, snapshot_id: str | None = None, expected_head: str | None = None) -> ReleaseBatchHistory:
    verify_history(history)
    if not isinstance(batch, batch_model.ReleaseBatch):
        raise ValidationError("release batch history append requires a typed batch")
    batch_model.verify_batch(batch)
    head = history.entries[-1].content_address if history.entries else ""
    if expected_head is not None and expected_head != head:
        raise ValidationError("release batch history expected head does not match")
    if history.entry_count >= MAX_ENTRIES:
        raise ValidationError("release batch history is full")
    if batch.content_address in {item.batch_address for item in history.entries} or batch.batch_id in {item.batch_id for item in history.entries}:
        raise ValidationError("release batch history rejects duplicate batch identity or address")
    previous = history.entries[-1] if history.entries else None
    if previous is None:
        transition = "initial"
    elif batch.release_ready and not previous.release_ready:
        transition = "promoted"
    elif previous.release_ready and not batch.release_ready:
        transition = "regressed"
    elif (batch.state, batch.item_count, batch.ready_count, batch.blocked_count) == (previous.state, previous.item_count, previous.ready_count, previous.blocked_count):
        transition = "unchanged"
    else:
        transition = "changed"
    identifier = snapshot_id or f"snapshot-{history.entry_count + 1:04d}"
    if identifier in {item.snapshot_id for item in history.entries}:
        raise ValidationError("release batch history rejects duplicate snapshot identity")
    return _history(history.history_id, history.entries + (_entry(batch, history.entry_count + 1, identifier, transition, head),))


def verify_history(value: ReleaseBatchHistory) -> ReleaseBatchHistory:
    if not isinstance(value, ReleaseBatchHistory):
        raise ValidationError("release batch history verification requires a typed history")
    value._validate()
    for index, item in enumerate(value.entries[1:], 2):
        if item.previous_address != value.entries[index - 2].content_address:
            raise ValidationError("release batch history previous address chain does not replay")
    return value


def history_from_mapping(value: Mapping[str, Any]) -> ReleaseBatchHistory:
    return ReleaseBatchHistory.from_mapping(value)


def history_json(value: ReleaseBatchHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def entries_json(value: ReleaseBatchHistory) -> str:
    value = verify_history(value)
    return canonical_json({"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)})


def manifest_json(value: ReleaseBatchHistory) -> str:
    return canonical_json(verify_history(value).manifest.to_dict())


def summary_json(value: ReleaseBatchHistory) -> str:
    return canonical_json(verify_history(value).summary.to_dict())


def history_csv(value: ReleaseBatchHistory) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ENTRY_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_history(value).entries)
    return output.getvalue()


def render_history_markdown(value: ReleaseBatchHistory) -> str:
    value = verify_history(value)
    lines = [f"# Release batch history {value.history_id}", "", f"- Latest state: {value.latest_state}", f"- Latest release ready: {str(value.latest_release_ready).lower()}", f"- Entries: {value.entry_count}", f"- Promoted: {value.promoted_count}", f"- Regressed: {value.regressed_count}", "", "| Snapshot | Batch | State | Transition | Ready |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.snapshot_id} | {item.batch_id} | {item.state} | {item.transition} | {str(item.release_ready).lower()} |" for item in value.entries)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_history(value: ReleaseBatchHistory, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_history(value)
    destination = Path(destination)
    _validate_parent(destination.parent, "release batch history destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("release batch history destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-release-batch-history-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "history.json": value.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("release batch history destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = _strict_json_loads(read_text(path, field="release batch history artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("release batch history artifact is not valid JSON") from error
    return _mapping(value, "release batch history artifact")


def load_history(destination: str | Path) -> ReleaseBatchHistory:
    destination = Path(destination)
    _validate_parent(destination.parent, "release batch history input")
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("release batch history source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("release batch history directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="release batch history artifact") != serialized or len(serialized.encode("utf-8")) > MAX_HISTORY_BYTES:
            raise ValidationError("release batch history artifact is non-canonical or exceeds its size bound")
    value = history_from_mapping(documents["history.json"])
    expected = {"manifest.json": value.manifest.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()):
        raise ValidationError("release batch history component documents do not replay history.json")
    return verify_history(value)


def run_history(batch: batch_model.ReleaseBatch, *, history_id: str = DEFAULT_HISTORY_ID, snapshot_id: str = "initial", destination: str | Path | None = None, overwrite: bool = False) -> ReleaseBatchHistory:
    value = build_history(batch, history_id=history_id, snapshot_id=snapshot_id)
    if destination is not None:
        persist_history(value, destination, overwrite=overwrite)
    return value


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchHistoryEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "integer" if field in ("ordinal", "item_count", "ready_count", "blocked_count") else "boolean" if field == "release_ready" else "string"} for field in ENTRY_FIELDS}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchHistoryEntries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "items": {"$ref": "#/$defs/entry"}}, "content_address": {"type": "string"}}, "$defs": {"entry": entry_schema()}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchHistoryManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchHistorySummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("latest_release_ready", "accepted") else "string"} for field in SUMMARY_FIELDS}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchHistory", "type": "object", "additionalProperties": False, "required": list(HISTORY_FIELDS), "properties": {field: {"type": "array" if field == "entries" else "object" if field in ("manifest", "summary") else "integer" if field.endswith("count") else "boolean" if field in ("latest_release_ready", "accepted") else "string"} for field in HISTORY_FIELDS}, "$defs": {"entry": entry_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "states": STATES, "transitions": TRANSITIONS, "max_entries": MAX_ENTRIES, "features": ("append-only release batch snapshots", "stable history identity", "optimistic expected-head appends", "duplicate batch and snapshot rejection", "promotion and regression transitions", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "HISTORY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_HISTORY_ID", "FILES", "ARTIFACT_FILES", "STATES", "TRANSITIONS", "MAX_ENTRIES", "MAX_HISTORY_BYTES", "ENTRY_FIELDS", "ENTRIES_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "HISTORY_FIELDS", "BatchHistoryEntry", "BatchHistoryEntries", "BatchHistoryManifest", "BatchHistorySummary", "ReleaseBatchHistory", "address_entry", "address_entries", "address_manifest", "address_summary", "address_history", "build_history", "append_history", "verify_history", "history_from_mapping", "history_json", "entries_json", "manifest_json", "summary_json", "history_csv", "render_history_markdown", "persist_history", "load_history", "run_history", "entry_schema", "entries_schema", "manifest_schema", "summary_schema", "history_schema", "capabilities"]
