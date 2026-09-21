"""Baseline/candidate diff for runtime registry histories."""

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

from . import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history as history_model
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
SUMMARY_FIELDS = ("diff_id", "registry_id", "left_history_id", "right_history_id", "left_history_address", "right_history_address", "left_entry_count", "right_entry_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "state_transition", "accepted", "content_address")
DIFF_FIELDS = ("diff_id", "registry_id", "version", "boundary", "left_history_id", "right_history_id", "left_history_address", "right_history_address", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "state_transition", "accepted", "manifest", "summary", "items", "content_address")


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
    return history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _snapshot(value: Any, field: str, *, required: bool) -> dict[str, Any]:
    if value is None and not required:
        return {}
    value = _mapping(value, field)
    if len(canonical_json(value).encode("utf-8")) > 32768 or not _public(value):
        raise ValidationError(f"{field} is too large or crosses the public boundary")
    return dict(value)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class DiffItem:
    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, identity: str, change: str, changed_fields: Sequence[str], left_entry_address: str, right_entry_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history diff item ordinal", MAX_ITEMS, lower=1)
        self.identity = _label(identity, "runtime registry history diff item identity")
        if change not in CHANGES:
            raise ValidationError("runtime registry history diff item change is unsupported")
        self.change = change
        allowed = tuple(field for field in history_model.ENTRY_FIELDS if field != "content_address")
        self.changed_fields = tuple(_label(item, "runtime registry history diff changed field") for item in _sequence(changed_fields, "runtime registry history diff changed fields", len(allowed)))
        if len(set(self.changed_fields)) != len(self.changed_fields) or any(field not in allowed for field in self.changed_fields) or self.changed_fields != tuple(field for field in allowed if field in self.changed_fields):
            raise ValidationError("runtime registry history diff changed fields are unsupported or unordered")
        self.left_entry_address = _address(left_entry_address, "runtime registry history diff left entry address", history_model.ENTRY_PREFIX, required=False)
        self.right_entry_address = _address(right_entry_address, "runtime registry history diff right entry address", history_model.ENTRY_PREFIX, required=False)
        self.left_snapshot = _snapshot(left_snapshot, "runtime registry history diff left snapshot", required=False)
        self.right_snapshot = _snapshot(right_snapshot, "runtime registry history diff right snapshot", required=False)
        self.content_address = _address(content_address, "runtime registry history diff item address", ITEM_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.left_snapshot or self.left_entry_address or not self.right_snapshot or not self.right_entry_address):
            raise ValidationError("added diff items require only a right snapshot")
        if self.change == "removed" and (not self.left_snapshot or not self.left_entry_address or self.right_snapshot or self.right_entry_address):
            raise ValidationError("removed diff items require only a left snapshot")
        if self.change in ("changed", "unchanged") and (not self.left_snapshot or not self.right_snapshot or not self.left_entry_address or not self.right_entry_address):
            raise ValidationError("paired diff items require both snapshots")
        if self.change == "unchanged" and (self.changed_fields or self.left_snapshot != self.right_snapshot):
            raise ValidationError("unchanged diff items must have equal snapshots")
        if self.change == "changed" and (not self.changed_fields or self.left_snapshot == self.right_snapshot):
            raise ValidationError("changed diff items require field deltas")
        if self.change in ("added", "removed") and self.changed_fields:
            raise ValidationError("added and removed diff items cannot have changed fields")
        if not self.content_address.startswith("pending:") and _address_for(self, ITEM_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history diff item address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffItem":
        value = _mapping(value, "runtime registry history diff item")
        _strict(value, set(cls.FIELDS), "runtime registry history diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DiffItem) -> str:
    if not isinstance(value, DiffItem):
        raise ValidationError("runtime registry history diff item address requires a typed item")
    return _address_for(value, ITEM_PREFIX)


class DiffItems:
    FIELDS = ITEMS_FIELDS

    def __init__(self, items: Sequence[DiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.items = tuple(item if isinstance(item, DiffItem) else DiffItem.from_mapping(_mapping(item, "runtime registry history diff item")) for item in _sequence(items, "runtime registry history diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "runtime registry history diff items address", ITEMS_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or any(item.content_address != address_item(item) for item in self.items):
            raise ValidationError("runtime registry history diff item order or addresses do not replay")
        if not self.content_address.startswith("pending:") and address_items(self.items) != self.content_address:
            raise ValidationError("runtime registry history diff items address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff items cross the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffItems":
        value = _mapping(value, "runtime registry history diff items")
        _strict(value, set(cls.FIELDS), "runtime registry history diff items")
        return cls(value["items"], value["content_address"])


def address_items(value: Sequence[DiffItem]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DiffItem) for item in typed):
        raise ValidationError("runtime registry history diff items address requires typed items")
    return content_hash({"items": [item.to_dict() for item in typed]}, prefix=ITEMS_PREFIX)


class DiffManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, diff_id: str, left_history_id: str, right_history_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.diff_id = _label(diff_id, "runtime registry history diff manifest ID")
        self.left_history_id = _label(left_history_id, "runtime registry history diff left history ID")
        self.right_history_id = _label(right_history_id, "runtime registry history diff right history ID")
        self.version = _text(version, "runtime registry history diff manifest version", 1024)
        self.boundary = _text(boundary, "runtime registry history diff manifest boundary", 2048)
        self.files = tuple(_text(item, "runtime registry history diff manifest file", 128) for item in _sequence(files, "runtime registry history diff manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "runtime registry history diff manifest artifact address") for item in _sequence(artifact_addresses, "runtime registry history diff manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "runtime registry history diff manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime registry history diff manifest is not canonical")
        if not self.content_address.startswith("pending:") and address_manifest(self) != self.content_address:
            raise ValidationError("runtime registry history diff manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffManifest":
        value = _mapping(value, "runtime registry history diff manifest")
        _strict(value, set(cls.FIELDS), "runtime registry history diff manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DiffManifest) -> str:
    if not isinstance(value, DiffManifest):
        raise ValidationError("runtime registry history diff manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class DiffSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, diff_id: str, registry_id: str, left_history_id: str, right_history_id: str, left_history_address: str, right_history_address: str, left_entry_count: int, right_entry_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, state_transition: str, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "runtime registry history diff summary ID")
        self.registry_id = _label(registry_id, "runtime registry history diff summary registry ID")
        self.left_history_id = _label(left_history_id, "runtime registry history diff summary left history ID")
        self.right_history_id = _label(right_history_id, "runtime registry history diff summary right history ID")
        self.left_history_address = _address(left_history_address, "runtime registry history diff summary left history address", history_model.HISTORY_PREFIX)
        self.right_history_address = _address(right_history_address, "runtime registry history diff summary right history address", history_model.HISTORY_PREFIX)
        self.left_entry_count = _count(left_entry_count, "runtime registry history diff left entry count", history_model.MAX_ENTRIES)
        self.right_entry_count = _count(right_entry_count, "runtime registry history diff right entry count", history_model.MAX_ENTRIES)
        self.added_count = _count(added_count, "runtime registry history diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "runtime registry history diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "runtime registry history diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "runtime registry history diff unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS:
            raise ValidationError("runtime registry history diff direction is unsupported")
        self.direction = direction
        self.state_transition = _text(state_transition, "runtime registry history diff state transition", 128)
        self.accepted = _bool(accepted, "runtime registry history diff acceptance")
        self.content_address = _address(content_address, "runtime registry history diff summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.added_count + self.removed_count + self.changed_count + self.unchanged_count < max(self.left_entry_count, self.right_entry_count):
            raise ValidationError("runtime registry history diff summary counts are incomplete")
        if not self.content_address.startswith("pending:") and address_summary(self) != self.content_address:
            raise ValidationError("runtime registry history diff summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffSummary":
        value = _mapping(value, "runtime registry history diff summary")
        _strict(value, set(cls.FIELDS), "runtime registry history diff summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DiffSummary) -> str:
    if not isinstance(value, DiffSummary):
        raise ValidationError("runtime registry history diff summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class HistoryDiff:
    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, registry_id: str, version: str, boundary: str, left_history_id: str, right_history_id: str, left_history_address: str, right_history_address: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, state_transition: str, accepted: bool, manifest: Mapping[str, Any] | DiffManifest, summary: Mapping[str, Any] | DiffSummary, items: Sequence[DiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "runtime registry history diff ID")
        self.registry_id = _label(registry_id, "runtime registry history diff registry ID")
        self.version = _text(version, "runtime registry history diff version", 1024)
        self.boundary = _text(boundary, "runtime registry history diff boundary", 2048)
        self.left_history_id = _label(left_history_id, "runtime registry history diff left history ID")
        self.right_history_id = _label(right_history_id, "runtime registry history diff right history ID")
        self.left_history_address = _address(left_history_address, "runtime registry history diff left history address", history_model.HISTORY_PREFIX)
        self.right_history_address = _address(right_history_address, "runtime registry history diff right history address", history_model.HISTORY_PREFIX)
        self.item_count = _count(item_count, "runtime registry history diff item count", MAX_ITEMS)
        self.added_count = _count(added_count, "runtime registry history diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "runtime registry history diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "runtime registry history diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "runtime registry history diff unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS:
            raise ValidationError("runtime registry history diff direction is unsupported")
        self.direction = direction
        self.state_transition = _text(state_transition, "runtime registry history diff state transition", 128)
        self.accepted = _bool(accepted, "runtime registry history diff acceptance")
        self.manifest = manifest if isinstance(manifest, DiffManifest) else DiffManifest.from_mapping(_mapping(manifest, "runtime registry history diff manifest"))
        self.summary = summary if isinstance(summary, DiffSummary) else DiffSummary.from_mapping(_mapping(summary, "runtime registry history diff summary"))
        self.items = tuple(item if isinstance(item, DiffItem) else DiffItem.from_mapping(_mapping(item, "runtime registry history diff item")) for item in _sequence(items, "runtime registry history diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "runtime registry history diff address", DIFF_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.item_count != len(self.items):
            raise ValidationError("runtime registry history diff identity or count does not replay")
        counts = tuple(sum(item.change == change for item in self.items) for change in CHANGES)
        if counts != (self.added_count, self.removed_count, self.changed_count, self.unchanged_count):
            raise ValidationError("runtime registry history diff change counts do not replay")
        if any(item.ordinal != index for index, item in enumerate(self.items, 1)) or any(item.content_address != address_item(item) for item in self.items):
            raise ValidationError("runtime registry history diff item order or address does not replay")
        expected_summary = (self.diff_id, self.registry_id, self.left_history_id, self.right_history_id, self.left_history_address, self.right_history_address, self.summary.left_entry_count, self.summary.right_entry_count, self.added_count, self.removed_count, self.changed_count, self.unchanged_count, self.direction, self.state_transition, self.accepted)
        actual_summary = tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1])
        if actual_summary != expected_summary or self.summary.content_address != address_summary(self.summary):
            raise ValidationError("runtime registry history diff summary does not replay")
        expected_manifest = (self.diff_id, self.left_history_id, self.right_history_id, VERSION, BOUNDARY, FILES, (address_items(self.items), self.summary.content_address))
        actual_manifest = (self.manifest.diff_id, self.manifest.left_history_id, self.manifest.right_history_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest):
            raise ValidationError("runtime registry history diff manifest does not replay")
        if not self.content_address.startswith("pending:") and address_diff(self) != self.content_address:
            raise ValidationError("runtime registry history diff address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "left_history_id": self.left_history_id, "right_history_id": self.right_history_id, "left_history_address": self.left_history_address, "right_history_address": self.right_history_address, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "direction": self.direction, "state_transition": self.state_transition, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "items": [item.to_dict() for item in self.items], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryDiff":
        value = _mapping(value, "runtime registry history diff")
        _strict(value, set(cls.FIELDS), "runtime registry history diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: HistoryDiff) -> str:
    if not isinstance(value, HistoryDiff):
        raise ValidationError("runtime registry history diff address requires a typed diff")
    return _address_for(value, DIFF_PREFIX)


def _quality(history: history_model.RegistryHistory) -> tuple[int, int, int, int]:
    ranks = {"ready": 0, "blocked": 1, "empty": 2}
    return (ranks[history.latest_state], 0 if history.latest_release_ready else 1, history.regressed_count, history.changed_count)


def _direction(left: history_model.RegistryHistory, right: history_model.RegistryHistory, item_changed: bool) -> str:
    if _quality(right) < _quality(left):
        return "improved"
    if _quality(right) > _quality(left):
        return "regressed"
    return "changed" if item_changed else "unchanged"


def build_diff(left: history_model.RegistryHistory, right: history_model.RegistryHistory, *, diff_id: str = DEFAULT_DIFF_ID) -> HistoryDiff:
    history_model.verify_history(left)
    history_model.verify_history(right)
    if left.registry_id != right.registry_id:
        raise ValidationError("runtime registry history diff requires matching registry identity")
    left_by = {item.ordinal: item for item in left.entries}
    right_by = {item.ordinal: item for item in right.entries}
    items: list[DiffItem] = []
    allowed = tuple(field for field in history_model.ENTRY_FIELDS if field != "content_address")
    for ordinal in range(1, max(len(left.entries), len(right.entries)) + 1):
        old = left_by.get(ordinal)
        new = right_by.get(ordinal)
        if old is None:
            change = "added"; changed = (); old_address = ""; new_address = new.content_address; old_snapshot = {}; new_snapshot = new.to_dict()
        elif new is None:
            change = "removed"; changed = (); old_address = old.content_address; new_address = ""; old_snapshot = old.to_dict(); new_snapshot = {}
        else:
            old_snapshot = old.to_dict(); new_snapshot = new.to_dict(); changed = tuple(field for field in allowed if old_snapshot[field] != new_snapshot[field]); change = "changed" if changed else "unchanged"; old_address = old.content_address; new_address = new.content_address
        body = {"ordinal": ordinal, "identity": f"ordinal-{ordinal}", "change": change, "changed_fields": changed, "left_entry_address": old_address, "right_entry_address": new_address, "left_snapshot": old_snapshot, "right_snapshot": new_snapshot, "content_address": f"pending:{ITEM_PREFIX}"}
        provisional = DiffItem(**body)
        items.append(DiffItem(**(body | {"content_address": address_item(provisional)})))
    added = sum(item.change == "added" for item in items); removed = sum(item.change == "removed" for item in items); changed = sum(item.change == "changed" for item in items); unchanged = sum(item.change == "unchanged" for item in items)
    direction = _direction(left, right, added + removed + changed > 0)
    accepted = left.accepted and right.accepted
    state_transition = f"{left.latest_state}->{right.latest_state}"
    summary = _seal(DiffSummary(diff_id, left.registry_id, left.history_id, right.history_id, left.content_address, right.content_address, left.entry_count, right.entry_count, added, removed, changed, unchanged, direction, state_transition, accepted, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(DiffManifest(diff_id, left.history_id, right.history_id, VERSION, BOUNDARY, FILES, (address_items(items), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(HistoryDiff(diff_id, left.registry_id, VERSION, BOUNDARY, left.history_id, right.history_id, left.content_address, right.content_address, len(items), added, removed, changed, unchanged, direction, state_transition, accepted, manifest, summary, items, f"pending:{DIFF_PREFIX}"), address_diff)


def verify_diff(value: HistoryDiff) -> HistoryDiff:
    if not isinstance(value, HistoryDiff):
        raise ValidationError("runtime registry history diff verification requires a typed diff")
    value._validate()
    return value


def diff_from_mapping(value: Mapping[str, Any]) -> HistoryDiff:
    return HistoryDiff.from_mapping(value)


def diff_json(value: HistoryDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def items_json(value: HistoryDiff) -> str:
    value = verify_diff(value)
    return canonical_json({"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)})


def manifest_json(value: HistoryDiff) -> str:
    return canonical_json(verify_diff(value).manifest.to_dict())


def summary_json(value: HistoryDiff) -> str:
    return canonical_json(verify_diff(value).summary.to_dict())


def diff_csv(value: HistoryDiff) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ITEM_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_diff(value).items); return output.getvalue()


def render_diff_markdown(value: HistoryDiff) -> str:
    value = verify_diff(value)
    lines = [f"# Runtime registry history diff {value.diff_id}", "", f"- Direction: {value.direction}", f"- State transition: {value.state_transition}", f"- Items: {value.item_count}", f"- Added: {value.added_count}", f"- Removed: {value.removed_count}", f"- Changed: {value.changed_count}", f"- Unchanged: {value.unchanged_count}", "", "| Ordinal | Change | Fields |", "| ---: | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.change} | {', '.join(item.changed_fields) or '—'} |" for item in value.items)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_diff(value: HistoryDiff, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_diff(value); destination = Path(destination); _validate_parent(destination.parent, "runtime registry history diff destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("runtime registry history diff destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True); temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-runtime-registry-history-diff-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "diff.json": value.to_dict(), "items.json": {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES: _write(temporary / name, documents[name])
        if destination.exists(): shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True); raise ValidationError("runtime registry history diff destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try: value = _strict_json_loads(read_text(path, field="runtime registry history diff artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error: raise ValidationError("runtime registry history diff artifact is not valid JSON") from error
    return _mapping(value, "runtime registry history diff artifact")


def load_diff(destination: str | Path) -> HistoryDiff:
    destination = Path(destination); _validate_parent(destination.parent, "runtime registry history diff input")
    if not destination.is_dir() or destination.is_symlink(): raise ValidationError("runtime registry history diff source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children): raise ValidationError("runtime registry history diff directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="runtime registry history diff artifact") != serialized or len(serialized.encode("utf-8")) > MAX_DIFF_BYTES: raise ValidationError("runtime registry history diff artifact is non-canonical or exceeds its size bound")
    value = diff_from_mapping(documents["diff.json"])
    expected = {"manifest.json": value.manifest.to_dict(), "items.json": {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()): raise ValidationError("runtime registry history diff component documents do not replay diff.json")
    return verify_diff(value)


def run_diff(left: history_model.RegistryHistory, right: history_model.RegistryHistory, *, diff_id: str = DEFAULT_DIFF_ID, destination: str | Path | None = None, overwrite: bool = False) -> HistoryDiff:
    value = build_diff(left, right, diff_id=diff_id)
    if destination is not None: persist_diff(value, destination, overwrite=overwrite)
    return value


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffItem", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "array" if field == "changed_fields" else "object" if field in ("left_snapshot", "right_snapshot") else "string"} for field in ITEM_FIELDS}}


def items_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffItems", "type": "object", "additionalProperties": False, "required": list(ITEMS_FIELDS), "properties": {"items": {"type": "array", "items": {"$ref": "#/$defs/item"}}, "content_address": {"type": "string"}}, "$defs": {"item": item_schema()}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in SUMMARY_FIELDS}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {field: {"type": "array" if field == "items" else "object" if field in ("manifest", "summary") else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in DIFF_FIELDS}, "$defs": {"item": item_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "changes": CHANGES, "directions": DIRECTIONS, "max_items": MAX_ITEMS, "features": ("ordinal baseline/candidate comparison", "field-level snapshot deltas", "added removed changed unchanged classification", "direction and state-transition folding", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "DIFF_PREFIX", "ITEM_PREFIX", "ITEMS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_DIFF_ID", "FILES", "ARTIFACT_FILES", "CHANGES", "DIRECTIONS", "MAX_ITEMS", "MAX_DIFF_BYTES", "ITEM_FIELDS", "ITEMS_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "DIFF_FIELDS", "DiffItem", "DiffItems", "DiffManifest", "DiffSummary", "HistoryDiff", "address_item", "address_items", "address_manifest", "address_summary", "address_diff", "build_diff", "verify_diff", "diff_from_mapping", "diff_json", "items_json", "manifest_json", "summary_json", "diff_csv", "render_diff_markdown", "persist_diff", "load_diff", "run_diff", "item_schema", "items_schema", "manifest_schema", "summary_schema", "diff_schema", "capabilities"]


