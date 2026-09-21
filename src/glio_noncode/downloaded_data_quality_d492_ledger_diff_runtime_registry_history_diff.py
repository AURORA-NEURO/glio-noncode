"""Baseline/candidate comparison for D491 runtime registry histories."""
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

from . import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = history_model.VERSION + "-diff-v1"
BOUNDARY = history_model.BOUNDARY + "_diff"
DIFF_PREFIX = history_model.HISTORY_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
ITEMS_PREFIX = DIFF_PREFIX + "-items"
MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
SUMMARY_PREFIX = DIFF_PREFIX + "-summary"
DEFAULT_DIFF_ID = DIFF_PREFIX
FILES = ("manifest.json", "diff.json", "items.json", "summary.json")
ARTIFACT_FILES = ("items.json", "summary.json")
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "changed", "unchanged")
MAX_ITEMS = history_model.MAX_ENTRIES * 2
MAX_DIFF_BYTES = 32 * 1024 * 1024
ITEM_FIELDS = ("ordinal", "identity", "change", "changed_fields", "left_entry_address", "right_entry_address", "left_snapshot", "right_snapshot", "content_address")
ITEMS_FIELDS = ("items", "content_address")
MANIFEST_FIELDS = ("diff_id", "left_history_id", "right_history_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("diff_id", "left_history_id", "right_history_id", "left_history_address", "right_history_address", "left_entry_count", "right_entry_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "state_transition", "accepted", "content_address")
DIFF_FIELDS = ("diff_id", "version", "boundary", "left_history_id", "right_history_id", "left_history_address", "right_history_address", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "state_transition", "accepted", "manifest", "summary", "items", "content_address")

def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(c) < 32 and c not in "\n\t" for c in value): raise ValidationError(f"{field} must be bounded public text")
    return value
def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(c.isspace() for c in value) or "/" in value or "\\" in value or '"' in value): raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if not value or value.startswith("pending:") or value.endswith(":pending"): return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")): raise ValidationError(f"{field} has the wrong address namespace")
    return value
def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= maximum: raise ValidationError(f"{field} is outside its bound")
    return value
def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool): raise ValidationError(f"{field} must be boolean")
    return value
def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)
def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValidationError(f"{field} must be an object")
    return value
def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed: raise ValidationError(f"{field} contains unknown or missing fields")
def _public(value: Any) -> bool: return history_model.registry_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value
def _snapshot(value: Any, field: str, *, required: bool) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        if not required and value == {}: return {}
        raise ValidationError(f"{field} must be an object")
    if not required and not value: return {}
    _strict(value, set(history_model.ENTRY_FIELDS), field)
    result = dict(value)
    entry = history_model.RegistryHistoryEntry.from_mapping(result)
    if entry.to_dict() != result: raise ValidationError(f"{field} is not a canonical typed history entry")
    if not _public(result): raise ValidationError(f"{field} crosses the public boundary")
    return result

class DiffItem:
    FIELDS = ITEM_FIELDS
    def __init__(self, ordinal: int, identity: str, change: str, changed_fields: Sequence[str], left_entry_address: str, right_entry_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "D492 item ordinal", MAX_ITEMS, lower=1); self.identity = _label(identity, "D492 item identity")
        if change not in CHANGES: raise ValidationError("D492 change is unsupported")
        self.change = change; self.changed_fields = tuple(_label(x, "D492 changed field") for x in _sequence(changed_fields, "D492 changed fields", len(history_model.ENTRY_FIELDS)))
        self.left_entry_address = _address(left_entry_address, "D492 left entry address", history_model.ENTRY_PREFIX, required=False); self.right_entry_address = _address(right_entry_address, "D492 right entry address", history_model.ENTRY_PREFIX, required=False)
        self.left_snapshot = _snapshot(left_snapshot, "D492 left snapshot", required=False); self.right_snapshot = _snapshot(right_snapshot, "D492 right snapshot", required=False)
        self.content_address = _address(content_address, "D492 item address", ITEM_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.change == "added" and (self.left_snapshot or not self.right_snapshot or self.left_entry_address or not self.right_entry_address): raise ValidationError("D492 added item does not replay")
        if self.change == "removed" and (not self.left_snapshot or self.right_snapshot or not self.left_entry_address or self.right_entry_address): raise ValidationError("D492 removed item does not replay")
        if self.change in ("changed", "unchanged") and (not self.left_snapshot or not self.right_snapshot or not self.left_entry_address or not self.right_entry_address): raise ValidationError("D492 matched item does not replay")
        if self.change == "changed":
            actual = tuple(f for f in history_model.ENTRY_FIELDS if f != "content_address" and self.left_snapshot.get(f) != self.right_snapshot.get(f))
            if not actual or actual != self.changed_fields: raise ValidationError("D492 changed fields do not replay")
        if self.change == "unchanged" and (self.changed_fields or self.left_snapshot != self.right_snapshot): raise ValidationError("D492 unchanged item contains a delta")
        if self.change in ("added", "removed") and self.changed_fields: raise ValidationError("D492 added/removed item cannot contain deltas")
        if (self.left_snapshot and (self.left_snapshot.get("snapshot_id") != self.identity or self.left_snapshot.get("content_address") != self.left_entry_address)) or (self.right_snapshot and (self.right_snapshot.get("snapshot_id") != self.identity or self.right_snapshot.get("content_address") != self.right_entry_address)): raise ValidationError("D492 snapshot identity or entry address does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, ITEM_PREFIX) != self.content_address: raise ValidationError("D492 item address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D492 item crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: list(getattr(self, field)) if field == "changed_fields" else getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffItem":
        value = _mapping(value, "D492 item"); _strict(value, set(cls.FIELDS), "D492 item"); return cls(*(value[f] for f in cls.FIELDS))

def address_item(value: DiffItem) -> str:
    if not isinstance(value, DiffItem): raise ValidationError("D492 addressing requires a typed item")
    return _address_for(value, ITEM_PREFIX)

class DiffItems:
    FIELDS = ITEMS_FIELDS
    def __init__(self, items: Sequence[DiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.items = tuple(x if isinstance(x, DiffItem) else DiffItem.from_mapping(_mapping(x, "D492 item")) for x in _sequence(items, "D492 items", MAX_ITEMS)); self.content_address = _address(content_address, "D492 items address", ITEMS_PREFIX); self._validate()
    def _validate(self) -> None:
        if tuple(x.ordinal for x in self.items) != tuple(range(1, len(self.items) + 1)) or len({x.identity for x in self.items}) != len(self.items): raise ValidationError("D492 item identity or order does not replay")
        if not self.content_address.startswith("pending:") and address_items(self.items) != self.content_address: raise ValidationError("D492 items address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D492 items cross the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"items": [x.to_dict() for x in self.items], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffItems":
        value = _mapping(value, "D492 items"); _strict(value, set(cls.FIELDS), "D492 items"); return cls(value["items"], value["content_address"])

def address_items(value: Sequence[DiffItem]) -> str:
    items = tuple(value)
    if any(not isinstance(x, DiffItem) for x in items): raise ValidationError("D492 items addressing requires typed items")
    return content_hash({"items": [x.to_dict() for x in items]}, prefix=ITEMS_PREFIX)

class DiffManifest:
    FIELDS = MANIFEST_FIELDS
    def __init__(self, diff_id: str, left_history_id: str, right_history_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.diff_id = _label(diff_id, "D492 manifest diff ID"); self.left_history_id = _label(left_history_id, "D492 manifest left history ID"); self.right_history_id = _label(right_history_id, "D492 manifest right history ID"); self.version = _text(version, "D492 manifest version", 1024); self.boundary = _text(boundary, "D492 manifest boundary", 2048); self.files = tuple(_text(x, "D492 manifest file", 128) for x in _sequence(files, "D492 files", len(FILES))); self.artifact_addresses = tuple(_address(x, "D492 manifest artifact") for x in _sequence(artifact_addresses, "D492 artifact addresses", len(ARTIFACT_FILES))); self.content_address = _address(content_address, "D492 manifest address", MANIFEST_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or (self.version, self.boundary) != (VERSION, BOUNDARY): raise ValidationError("D492 manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address: raise ValidationError("D492 manifest address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D492 manifest crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: list(getattr(self, field)) if field in ("files", "artifact_addresses") else getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffManifest":
        value = _mapping(value, "D492 manifest"); _strict(value, set(cls.FIELDS), "D492 manifest"); return cls(*(value[f] for f in cls.FIELDS))

def address_manifest(value: DiffManifest) -> str:
    if not isinstance(value, DiffManifest): raise ValidationError("D492 addressing requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)

class DiffSummary:
    FIELDS = SUMMARY_FIELDS
    def __init__(self, diff_id: str, left_history_id: str, right_history_id: str, left_history_address: str, right_history_address: str, left_entry_count: int, right_entry_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, state_transition: str, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "D492 summary ID"); self.left_history_id = _label(left_history_id, "D492 left history ID"); self.right_history_id = _label(right_history_id, "D492 right history ID"); self.left_history_address = _address(left_history_address, "D492 left history address", history_model.HISTORY_PREFIX); self.right_history_address = _address(right_history_address, "D492 right history address", history_model.HISTORY_PREFIX); self.left_entry_count = _count(left_entry_count, "D492 left count", history_model.MAX_ENTRIES); self.right_entry_count = _count(right_entry_count, "D492 right count", history_model.MAX_ENTRIES)
        self.added_count = _count(added_count, "D492 added count", MAX_ITEMS); self.removed_count = _count(removed_count, "D492 removed count", MAX_ITEMS); self.changed_count = _count(changed_count, "D492 changed count", MAX_ITEMS); self.unchanged_count = _count(unchanged_count, "D492 unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS: raise ValidationError("D492 direction is unsupported")
        self.direction = direction; self.state_transition = _text(state_transition, "D492 transition", 128); self.accepted = _bool(accepted, "D492 acceptance"); self.content_address = _address(content_address, "D492 summary address", SUMMARY_PREFIX); self._validate()
    def _validate(self) -> None:
        states = self.state_transition.split("->")
        if self.added_count + self.removed_count + self.changed_count + self.unchanged_count > MAX_ITEMS or len(states) != 2 or any(state not in history_model.STATES for state in states): raise ValidationError("D492 summary does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address: raise ValidationError("D492 summary address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D492 summary crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffSummary":
        value = _mapping(value, "D492 summary"); _strict(value, set(cls.FIELDS), "D492 summary"); return cls(*(value[f] for f in cls.FIELDS))

def address_summary(value: DiffSummary) -> str:
    if not isinstance(value, DiffSummary): raise ValidationError("D492 addressing requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)

class HistoryDiff:
    FIELDS = DIFF_FIELDS
    def __init__(self, diff_id: str, version: str, boundary: str, left_history_id: str, right_history_id: str, left_history_address: str, right_history_address: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, state_transition: str, accepted: bool, manifest: Mapping[str, Any] | DiffManifest, summary: Mapping[str, Any] | DiffSummary, items: Sequence[DiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "D492 diff ID"); self.version = _text(version, "D492 version", 1024); self.boundary = _text(boundary, "D492 boundary", 2048); self.left_history_id = _label(left_history_id, "D492 left history ID"); self.right_history_id = _label(right_history_id, "D492 right history ID"); self.left_history_address = _address(left_history_address, "D492 left address", history_model.HISTORY_PREFIX); self.right_history_address = _address(right_history_address, "D492 right address", history_model.HISTORY_PREFIX)
        self.item_count = _count(item_count, "D492 item count", MAX_ITEMS); self.added_count = _count(added_count, "D492 added count", MAX_ITEMS); self.removed_count = _count(removed_count, "D492 removed count", MAX_ITEMS); self.changed_count = _count(changed_count, "D492 changed count", MAX_ITEMS); self.unchanged_count = _count(unchanged_count, "D492 unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS: raise ValidationError("D492 direction is unsupported")
        self.direction = direction; self.state_transition = _text(state_transition, "D492 state transition", 128); self.accepted = _bool(accepted, "D492 acceptance"); self.manifest = manifest if isinstance(manifest, DiffManifest) else DiffManifest.from_mapping(_mapping(manifest, "D492 manifest")); self.summary = summary if isinstance(summary, DiffSummary) else DiffSummary.from_mapping(_mapping(summary, "D492 summary")); self.items = tuple(x if isinstance(x, DiffItem) else DiffItem.from_mapping(_mapping(x, "D492 item")) for x in _sequence(items, "D492 items", MAX_ITEMS)); self.content_address = _address(content_address, "D492 address", DIFF_PREFIX); self._validate()
    def _validate(self) -> None:
        if (self.version, self.boundary) != (VERSION, BOUNDARY) or self.left_history_id != self.right_history_id or self.item_count != len(self.items) or sum((self.added_count, self.removed_count, self.changed_count, self.unchanged_count)) != self.item_count: raise ValidationError("D492 identity or count conservation does not replay")
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != tuple(sum(x.change == c for x in self.items) for c in CHANGES): raise ValidationError("D492 change counters do not replay")
        if tuple(x.ordinal for x in self.items) != tuple(range(1, self.item_count + 1)) or len({x.identity for x in self.items}) != self.item_count: raise ValidationError("D492 item order or identity does not replay")
        expected = (self.diff_id, self.left_history_id, self.right_history_id, self.left_history_address, self.right_history_address, self.summary.left_entry_count, self.summary.right_entry_count, self.added_count, self.removed_count, self.changed_count, self.unchanged_count, self.direction, self.state_transition, self.accepted)
        if tuple(getattr(self.summary, f) for f in SUMMARY_FIELDS[:-1]) != expected or address_summary(self.summary) != self.summary.content_address: raise ValidationError("D492 summary does not replay")
        if self.accepted != bool(self.summary.left_entry_count and self.summary.right_entry_count and self.item_count): raise ValidationError("D492 acceptance does not replay source-history cardinality")
        expected_m = (self.diff_id, self.left_history_id, self.right_history_id, VERSION, BOUNDARY, FILES, (address_items(self.items), self.summary.content_address)); actual_m = (self.manifest.diff_id, self.manifest.left_history_id, self.manifest.right_history_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_m != expected_m or address_manifest(self.manifest) != self.manifest.content_address: raise ValidationError("D492 manifest does not replay")
        if not self.content_address.startswith("pending:") and address_diff(self) != self.content_address: raise ValidationError("D492 diff address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D492 diff crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "items": [x.to_dict() for x in self.items], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryDiff":
        value = _mapping(value, "D492 diff"); _strict(value, set(cls.FIELDS), "D492 diff"); return cls(*(value[f] for f in cls.FIELDS))

def address_diff(value: HistoryDiff) -> str:
    if not isinstance(value, HistoryDiff): raise ValidationError("D492 addressing requires a typed diff")
    return _address_for(value, DIFF_PREFIX)

def _direction(left: history_model.RuntimeRegistryHistory, right: history_model.RuntimeRegistryHistory, items: Sequence[DiffItem]) -> str:
    if left.latest_release_ready != right.latest_release_ready: return "improved" if right.latest_release_ready else "regressed"
    return "unchanged" if not any(x.change != "unchanged" for x in items) else "changed"

def build_diff(left: history_model.RuntimeRegistryHistory, right: history_model.RuntimeRegistryHistory, *, diff_id: str = DEFAULT_DIFF_ID) -> HistoryDiff:
    history_model.verify_history(left); history_model.verify_history(right)
    if left.history_id != right.history_id: raise ValidationError("D492 comparison requires the same history identity")
    left_by = {x.snapshot_id: x for x in left.entries}; right_by = {x.snapshot_id: x for x in right.entries}; identities = tuple(left_by) + tuple(x for x in right_by if x not in left_by); fields = tuple(x for x in history_model.ENTRY_FIELDS if x != "content_address"); items = []
    for ordinal, identity in enumerate(identities, 1):
        a = left_by.get(identity); b = right_by.get(identity); sa = a.to_dict() if a else {}; sb = b.to_dict() if b else {}; change = "added" if a is None else "removed" if b is None else "unchanged" if sa == sb else "changed"; delta = tuple(f for f in fields if sa.get(f) != sb.get(f)) if change == "changed" else ()
        body = {"ordinal": ordinal, "identity": identity, "change": change, "changed_fields": delta, "left_entry_address": a.content_address if a else "", "right_entry_address": b.content_address if b else "", "left_snapshot": sa, "right_snapshot": sb, "content_address": f"pending:{ITEM_PREFIX}"}; provisional = DiffItem(**body); items.append(DiffItem(**(body | {"content_address": address_item(provisional)})))
    added = sum(x.change == "added" for x in items); removed = sum(x.change == "removed" for x in items); changed = sum(x.change == "changed" for x in items); unchanged = sum(x.change == "unchanged" for x in items); direction = _direction(left, right, items); accepted = left.accepted and right.accepted and bool(items); transition = f"{left.latest_state}->{right.latest_state}"
    summary = _seal(DiffSummary(diff_id, left.history_id, right.history_id, left.content_address, right.content_address, left.entry_count, right.entry_count, added, removed, changed, unchanged, direction, transition, accepted, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(DiffManifest(diff_id, left.history_id, right.history_id, VERSION, BOUNDARY, FILES, (address_items(items), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(HistoryDiff(diff_id, VERSION, BOUNDARY, left.history_id, right.history_id, left.content_address, right.content_address, len(items), added, removed, changed, unchanged, direction, transition, accepted, manifest, summary, items, f"pending:{DIFF_PREFIX}"), address_diff)

def verify_diff(value: HistoryDiff) -> HistoryDiff:
    if not isinstance(value, HistoryDiff): raise ValidationError("D492 verification requires a typed diff")
    value._validate(); return value
def diff_from_mapping(value: Mapping[str, Any]) -> HistoryDiff: return HistoryDiff.from_mapping(value)
def diff_json(value: HistoryDiff) -> str: return canonical_json(verify_diff(value).to_dict())
def items_json(value: HistoryDiff) -> str:
    value = verify_diff(value); return canonical_json({"items": [x.to_dict() for x in value.items], "content_address": address_items(value.items)})
def manifest_json(value: HistoryDiff) -> str: return canonical_json(verify_diff(value).manifest.to_dict())
def summary_json(value: HistoryDiff) -> str: return canonical_json(verify_diff(value).summary.to_dict())
def diff_csv(value: HistoryDiff) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ITEM_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(x.to_dict() for x in verify_diff(value).items); return output.getvalue()
def render_diff_markdown(value: HistoryDiff) -> str:
    value = verify_diff(value); lines = [f"# Runtime registry history diff {value.diff_id}", "", f"- Direction: {value.direction}", f"- State transition: {value.state_transition}", f"- Added/removed/changed/unchanged: {value.added_count}/{value.removed_count}/{value.changed_count}/{value.unchanged_count}", "", "| Snapshot | Change | Changed fields |", "| --- | --- | --- |"]
    lines.extend(f"| {x.identity} | {x.change} | {', '.join(x.changed_fields)} |" for x in value.items); return "\n".join(lines) + "\n"

def _write(path: Path, value: Mapping[str, Any]) -> None: path.write_text(canonical_json(value), encoding="utf-8", newline="\n")
def persist_diff(value: HistoryDiff, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_diff(value); destination = Path(destination); _validate_parent(destination.parent, "D492 destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)): raise ValidationError("D492 destination exists or is not a regular directory")
    destination.parent.mkdir(parents=True, exist_ok=True); temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-d492-diff-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "diff.json": value.to_dict(), "items.json": {"items": [x.to_dict() for x in value.items], "content_address": address_items(value.items)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES: _write(temporary / name, documents[name])
        if destination.exists(): shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True); raise ValidationError("D492 destination could not be written") from error
    return destination

def _read_json(path: Path) -> Mapping[str, Any]:
    try: value = _strict_json_loads(read_text(path, field="D492 artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error: raise ValidationError("D492 artifact is not valid JSON") from error
    return _mapping(value, "D492 artifact")

def load_diff(destination: str | Path) -> HistoryDiff:
    destination = Path(destination); _validate_parent(destination.parent, "D492 input")
    if not destination.is_dir() or destination.is_symlink(): raise ValidationError("D492 source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(x.name for x in children)) != tuple(sorted(FILES)) or any(x.is_symlink() or not x.is_file() for x in children): raise ValidationError("D492 directory must contain exactly the regular artifact files")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        raw = canonical_json(document)
        if read_text(destination / name, field="D492 artifact") != raw or len(raw.encode("utf-8")) > MAX_DIFF_BYTES: raise ValidationError("D492 artifact is noncanonical or exceeds the size bound")
    value = diff_from_mapping(documents["diff.json"]); expected = {"manifest.json": value.manifest.to_dict(), "items.json": {"items": [x.to_dict() for x in value.items], "content_address": address_items(value.items)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()): raise ValidationError("D492 component documents do not replay the main document")
    return verify_diff(value)

def run_diff(left: history_model.RuntimeRegistryHistory, right: history_model.RuntimeRegistryHistory, *, diff_id: str = DEFAULT_DIFF_ID, destination: str | Path | None = None, overwrite: bool = False) -> HistoryDiff:
    value = build_diff(left, right, diff_id=diff_id)
    if destination is not None: persist_diff(value, destination, overwrite=overwrite)
    return value

def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryDiffItem", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {f: {"type": "integer" if f == "ordinal" else "array" if f == "changed_fields" else "object" if f in ("left_snapshot", "right_snapshot") else "string"} for f in ITEM_FIELDS}}
def items_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryDiffItems", "type": "object", "additionalProperties": False, "required": list(ITEMS_FIELDS), "properties": {"items": {"type": "array", "items": {"$ref": "#/$defs/item"}}, "content_address": {"type": "string"}}, "$defs": {"item": item_schema()}}
def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryDiffManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {f: {"type": "array" if f in ("files", "artifact_addresses") else "string"} for f in MANIFEST_FIELDS}}
def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryDiffSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {f: {"type": "integer" if f.endswith("count") else "boolean" if f == "accepted" else "string"} for f in SUMMARY_FIELDS}}
def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryDiff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {f: {"type": "array" if f == "items" else "object" if f in ("manifest", "summary") else "integer" if f.endswith("count") else "boolean" if f == "accepted" else "string"} for f in DIFF_FIELDS}, "$defs": {"item": item_schema()}}
def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "changes": CHANGES, "directions": DIRECTIONS, "max_items": MAX_ITEMS, "features": ("snapshot matching", "field-level history entry deltas", "added removed changed unchanged classification", "readiness and state-transition folding", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}

__all__ = ["VERSION", "BOUNDARY", "DIFF_PREFIX", "ITEM_PREFIX", "ITEMS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_DIFF_ID", "FILES", "ARTIFACT_FILES", "CHANGES", "DIRECTIONS", "MAX_ITEMS", "MAX_DIFF_BYTES", "ITEM_FIELDS", "ITEMS_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "DIFF_FIELDS", "DiffItem", "DiffItems", "DiffManifest", "DiffSummary", "HistoryDiff", "address_item", "address_items", "address_manifest", "address_summary", "address_diff", "build_diff", "verify_diff", "diff_from_mapping", "diff_json", "items_json", "manifest_json", "summary_json", "diff_csv", "render_diff_markdown", "persist_diff", "load_diff", "run_diff", "item_schema", "items_schema", "manifest_schema", "summary_schema", "diff_schema", "capabilities"]
