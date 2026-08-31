"""Deterministic baseline/candidate diff for history-diff archive-transfer recovery-execution runtime registries."""

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

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-diff-v1"
BOUNDARY = history_model.BOUNDARY + "_diff"
DIFF_PREFIX = history_model.HISTORY_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
ITEMS_PREFIX = DIFF_PREFIX + "-items"
MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
SUMMARY_PREFIX = DIFF_PREFIX + "-summary"
DEFAULT_DIFF_ID = DIFF_PREFIX
FILES = ("manifest.json", "diff.json", "items.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "changed", "unchanged")
MAX_ITEMS = history_model.MAX_ENTRIES * 2
MAX_DIFF_BYTES = 16 * 1024 * 1024
ITEM_FIELDS = (
    "ordinal",
    "identity",
    "change",
    "changed_fields",
    "left_entry_address",
    "right_entry_address",
    "left_snapshot",
    "right_snapshot",
    "content_address",
)
ITEMS_FIELDS = ("items", "content_address")
MANIFEST_FIELDS = ("diff_id", "left_history_id", "right_history_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = (
    "diff_id",
    "left_history_id",
    "right_history_id",
    "left_history_address",
    "right_history_address",
    "left_entry_count",
    "right_entry_count",
    "added_count",
    "removed_count",
    "changed_count",
    "unchanged_count",
    "direction",
    "accepted",
    "content_address",
)
DIFF_FIELDS = (
    "diff_id",
    "version",
    "boundary",
    "left_history_id",
    "right_history_id",
    "left_history_address",
    "right_history_address",
    "item_count",
    "added_count",
    "removed_count",
    "changed_count",
    "unchanged_count",
    "direction",
    "accepted",
    "manifest",
    "summary",
    "items",
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


def _signed(value: Any, field: str, bound: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < -bound or value > bound:
        raise ValidationError(f"{field} is outside its signed bound")
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


def _snapshot(value: Any, field: str, *, required: bool) -> dict[str, Any]:
    if value is None and not required:
        return {}
    value = _mapping(value, field)
    if len(canonical_json(value).encode("utf-8")) > 32768:
        raise ValidationError(f"{field} is too large")
    if not _public(value):
        raise ValidationError(f"{field} crosses the public boundary")
    return dict(value)


def _quality(value: history_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory) -> tuple[int, int, int, int, int, int]:
    ranks = {"ready": 0, "empty": 1, "blocked": 2}
    return (
        ranks[value.state],
        -value.latest_ready_count,
        -value.latest_accepted_count,
        value.latest_blocked_count,
        -value.latest_entry_count,
        value.entry_count,
    )


def _direction(left: history_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory, right: history_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory, item_change: bool) -> str:
    left_quality = _quality(left)
    right_quality = _quality(right)
    if right_quality < left_quality:
        return "improved"
    if right_quality > left_quality:
        return "regressed"
    return "changed" if item_change else "unchanged"


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem:
    """One stable-ordinal baseline/candidate history comparison."""

    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, identity: str, change: str, changed_fields: Sequence[str], left_entry_address: str, right_entry_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history diff item ordinal", MAX_ITEMS, lower=1)
        self.identity = _label(identity, "runtime registry history diff item identity")
        if change not in CHANGES:
            raise ValidationError("runtime registry history diff item change is unsupported")
        self.change = change
        self.changed_fields = tuple(_label(item, "runtime registry history diff changed field") for item in _sequence(changed_fields, "runtime registry history diff changed fields", len(ITEM_FIELDS)))
        allowed_fields = tuple(field for field in history_model.ENTRY_FIELDS if field != "content_address")
        if len(self.changed_fields) != len(set(self.changed_fields)) or any(field not in allowed_fields for field in self.changed_fields) or self.changed_fields != tuple(field for field in allowed_fields if field in self.changed_fields):
            raise ValidationError("runtime registry history diff changed fields must be unique and preserve contract order")
        self.left_entry_address = _address(left_entry_address, "runtime registry history diff left entry address", history_model.ENTRY_PREFIX, required=False)
        self.right_entry_address = _address(right_entry_address, "runtime registry history diff right entry address", history_model.ENTRY_PREFIX, required=False)
        self.left_snapshot = _snapshot(left_snapshot, "runtime registry history diff left snapshot", required=False)
        self.right_snapshot = _snapshot(right_snapshot, "runtime registry history diff right snapshot", required=False)
        self.content_address = _address(content_address, "runtime registry history diff item address", ITEM_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.left_snapshot or self.left_entry_address or not self.right_snapshot or not self.right_entry_address):
            raise ValidationError("added history diff items require only a right snapshot")
        if self.change == "removed" and (not self.left_snapshot or not self.left_entry_address or self.right_snapshot or self.right_entry_address):
            raise ValidationError("removed history diff items require only a left snapshot")
        if self.change in ("changed", "unchanged") and (not self.left_snapshot or not self.right_snapshot or not self.left_entry_address or not self.right_entry_address):
            raise ValidationError("paired history diff items require both snapshots")
        if self.change == "unchanged" and (self.changed_fields or self.left_snapshot != self.right_snapshot):
            raise ValidationError("unchanged history diff items must have equal snapshots")
        if self.change == "changed" and (not self.changed_fields or self.left_snapshot == self.right_snapshot):
            raise ValidationError("changed history diff items require field deltas")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff item crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("runtime registry history diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem:
        value = _mapping(value, "runtime registry history diff item")
        _strict(value, set(cls.FIELDS), "runtime registry history diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem):
        raise ValidationError("runtime registry history diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItems:
    """Ordered and addressed diff-item projection."""

    FIELDS = ITEMS_FIELDS

    def __init__(self, items: Sequence[HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.items = tuple(item if isinstance(item, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem) else HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem.from_mapping(item) for item in _sequence(items, "runtime registry history diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "runtime registry history diff items address", ITEMS_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            raise ValidationError("runtime registry history diff item ordinals must be contiguous")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff items cross the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_items(self.items) != self.content_address:
            raise ValidationError("runtime registry history diff items address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItems:
        value = _mapping(value, "runtime registry history diff items")
        _strict(value, set(cls.FIELDS), "runtime registry history diff items")
        return cls(value["items"], value["content_address"])


def address_items(value: Sequence[HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem) for item in typed):
        raise ValidationError("runtime registry history diff items address requires typed items")
    return content_hash([item.to_dict() for item in typed], prefix=ITEMS_PREFIX)


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest:
    """Canonical package manifest for a history diff."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, diff_id: str, left_history_id: str, right_history_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.diff_id = _label(diff_id, "runtime registry history diff ID")
        self.left_history_id = _label(left_history_id, "runtime registry history diff left history ID", required=False)
        self.right_history_id = _label(right_history_id, "runtime registry history diff right history ID", required=False)
        self.version = _text(version, "runtime registry history diff version", 1024)
        self.boundary = _text(boundary, "runtime registry history diff boundary", 1024)
        self.files = tuple(_label(item, "runtime registry history diff manifest file") for item in _sequence(files, "runtime registry history diff manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "runtime registry history diff manifest artifact address") for item in _sequence(artifact_addresses, "runtime registry history diff manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "runtime registry history diff manifest address", MANIFEST_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.files != FILES or len(self.artifact_addresses) != 2:
            raise ValidationError("runtime registry history diff manifest contract does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff manifest crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("runtime registry history diff manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest:
        value = _mapping(value, "runtime registry history diff manifest")
        _strict(value, set(cls.FIELDS), "runtime registry history diff manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest):
        raise ValidationError("runtime registry history diff manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary:
    """Compact metrics and direction projection for a history diff."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, diff_id: str, left_history_id: str, right_history_id: str, left_history_address: str, right_history_address: str, left_entry_count: int, right_entry_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "runtime registry history diff summary ID")
        self.left_history_id = _label(left_history_id, "runtime registry history diff summary left history ID", required=False)
        self.right_history_id = _label(right_history_id, "runtime registry history diff summary right history ID", required=False)
        self.left_history_address = _address(left_history_address, "runtime registry history diff summary left history address", history_model.HISTORY_PREFIX, required=False)
        self.right_history_address = _address(right_history_address, "runtime registry history diff summary right history address", history_model.HISTORY_PREFIX, required=False)
        self.left_entry_count = _count(left_entry_count, "runtime registry history diff left entry count", history_model.MAX_ENTRIES)
        self.right_entry_count = _count(right_entry_count, "runtime registry history diff right entry count", history_model.MAX_ENTRIES)
        self.added_count = _count(added_count, "runtime registry history diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "runtime registry history diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "runtime registry history diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "runtime registry history diff unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS:
            raise ValidationError("runtime registry history diff direction is unsupported")
        self.direction = direction
        self.accepted = _bool(accepted, "runtime registry history diff acceptance")
        self.content_address = _address(content_address, "runtime registry history diff summary address", SUMMARY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.added_count + self.removed_count + self.changed_count + self.unchanged_count > MAX_ITEMS:
            raise ValidationError("runtime registry history diff summary count exceeds bound")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff summary crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("runtime registry history diff summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary:
        value = _mapping(value, "runtime registry history diff summary")
        _strict(value, set(cls.FIELDS), "runtime registry history diff summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary):
        raise ValidationError("runtime registry history diff summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff:
    """Fully addressed baseline/candidate history comparison."""

    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, version: str, boundary: str, left_history_id: str, right_history_id: str, left_history_address: str, right_history_address: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, accepted: bool, manifest: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest | Mapping[str, Any], summary: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary | Mapping[str, Any], items: Sequence[HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "runtime registry history diff ID")
        self.version = _text(version, "runtime registry history diff version", 1024)
        self.boundary = _text(boundary, "runtime registry history diff boundary", 1024)
        self.left_history_id = _label(left_history_id, "runtime registry history diff left history ID", required=False)
        self.right_history_id = _label(right_history_id, "runtime registry history diff right history ID", required=False)
        self.left_history_address = _address(left_history_address, "runtime registry history diff left history address", history_model.HISTORY_PREFIX, required=False)
        self.right_history_address = _address(right_history_address, "runtime registry history diff right history address", history_model.HISTORY_PREFIX, required=False)
        self.item_count = _count(item_count, "runtime registry history diff item count", MAX_ITEMS)
        self.added_count = _count(added_count, "runtime registry history diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "runtime registry history diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "runtime registry history diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "runtime registry history diff unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS:
            raise ValidationError("runtime registry history diff direction is unsupported")
        self.direction = direction
        self.accepted = _bool(accepted, "runtime registry history diff acceptance")
        self.manifest = manifest if isinstance(manifest, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest) else HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary) else HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary.from_mapping(summary)
        self.items = tuple(item if isinstance(item, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem) else HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem.from_mapping(item) for item in _sequence(items, "runtime registry history diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "runtime registry history diff address", DIFF_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime registry history diff version or boundary does not replay")
        if self.item_count != len(self.items) or tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            raise ValidationError("runtime registry history diff item count or order does not replay")
        counts = {change: sum(item.change == change for item in self.items) for change in CHANGES}
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != tuple(counts[change] for change in CHANGES):
            raise ValidationError("runtime registry history diff change counts do not replay")
        if self.manifest.diff_id != self.diff_id or self.summary.diff_id != self.diff_id or self.summary.left_history_id != self.left_history_id or self.summary.right_history_id != self.right_history_id:
            raise ValidationError("runtime registry history diff component identity does not replay")
        if self.summary.left_history_address != self.left_history_address or self.summary.right_history_address != self.right_history_address or self.summary.added_count != self.added_count or self.summary.removed_count != self.removed_count or self.summary.changed_count != self.changed_count or self.summary.unchanged_count != self.unchanged_count or self.summary.direction != self.direction or self.summary.accepted != self.accepted:
            raise ValidationError("runtime registry history diff summary does not replay")
        if tuple(self.manifest.artifact_addresses) != (address_items(self.items), self.summary.content_address):
            raise ValidationError("runtime registry history diff manifest artifacts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("runtime registry history diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "version": self.version,
            "boundary": self.boundary,
            "left_history_id": self.left_history_id,
            "right_history_id": self.right_history_id,
            "left_history_address": self.left_history_address,
            "right_history_address": self.right_history_address,
            "item_count": self.item_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "changed_count": self.changed_count,
            "unchanged_count": self.unchanged_count,
            "direction": self.direction,
            "accepted": self.accepted,
            "manifest": self.manifest.to_dict(),
            "summary": self.summary.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "content_address": self.content_address,
        }

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "summary", "items"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff:
        value = _mapping(value, "runtime registry history diff")
        _strict(value, set(cls.FIELDS), "runtime registry history diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff):
        raise ValidationError("runtime registry history diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _identity(ordinal: int) -> str:
    return f"ordinal-{ordinal:08d}"


def _changed_fields(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(field for field in history_model.ENTRY_FIELDS if field != "content_address" and left.get(field) != right.get(field))


def _item(ordinal: int, left: history_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry | None, right: history_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryEntry | None) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem:
    if left is None and right is None:
        raise ValidationError("history diff item requires a baseline or candidate snapshot")
    if left is None:
        change = "added"
        left_address = ""
        right_address = right.content_address
        left_snapshot: Mapping[str, Any] = {}
        right_snapshot = right.to_dict()
        changed_fields: Sequence[str] = ()
    elif right is None:
        change = "removed"
        left_address = left.content_address
        right_address = ""
        left_snapshot = left.to_dict()
        right_snapshot = {}
        changed_fields = ()
    else:
        left_snapshot = left.to_dict()
        right_snapshot = right.to_dict()
        changed_fields = _changed_fields(left_snapshot, right_snapshot)
        change = "changed" if changed_fields else "unchanged"
        left_address = left.content_address
        right_address = right.content_address
    body = {
        "ordinal": ordinal,
        "identity": _identity(ordinal),
        "change": change,
        "changed_fields": changed_fields,
        "left_entry_address": left_address,
        "right_entry_address": right_address,
        "left_snapshot": left_snapshot,
        "right_snapshot": right_snapshot,
        "content_address": ITEM_PREFIX + ":pending",
    }
    provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem(**body)
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItem(**(body | {"content_address": address_item(provisional)}))


def build_diff(left: history_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory, right: history_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory, *, diff_id: str = DEFAULT_DIFF_ID) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff:
    left = history_model.verify_history(left)
    right = history_model.verify_history(right)
    if left.registry_id != right.registry_id:
        raise ValidationError("runtime registry history diffs require one registry identity")
    if not left.history_id or not right.history_id:
        raise ValidationError("runtime registry history diffs require named histories")
    item_count = max(left.entry_count, right.entry_count)
    items = tuple(_item(ordinal, left.entries[ordinal - 1] if ordinal <= left.entry_count else None, right.entries[ordinal - 1] if ordinal <= right.entry_count else None) for ordinal in range(1, item_count + 1))
    counts = {change: sum(item.change == change for item in items) for change in CHANGES}
    item_change = any(item.change != "unchanged" for item in items)
    direction = _direction(left, right, item_change)
    accepted = left.accepted and right.accepted
    summary_body = {
        "diff_id": diff_id,
        "left_history_id": left.history_id,
        "right_history_id": right.history_id,
        "left_history_address": left.content_address,
        "right_history_address": right.content_address,
        "left_entry_count": left.entry_count,
        "right_entry_count": right.entry_count,
        "added_count": counts["added"],
        "removed_count": counts["removed"],
        "changed_count": counts["changed"],
        "unchanged_count": counts["unchanged"],
        "direction": direction,
        "accepted": accepted,
        "content_address": SUMMARY_PREFIX + ":pending",
    }
    summary_provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary(**summary_body)
    summary = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    items_address = address_items(items)
    manifest_body = {
        "diff_id": diff_id,
        "left_history_id": left.history_id,
        "right_history_id": right.history_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "files": FILES,
        "artifact_addresses": (items_address, summary.content_address),
        "content_address": MANIFEST_PREFIX + ":pending",
    }
    manifest_provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest(**manifest_body)
    manifest = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {
        "diff_id": diff_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "left_history_id": left.history_id,
        "right_history_id": right.history_id,
        "left_history_address": left.content_address,
        "right_history_address": right.content_address,
        "item_count": len(items),
        "added_count": counts["added"],
        "removed_count": counts["removed"],
        "changed_count": counts["changed"],
        "unchanged_count": counts["unchanged"],
        "direction": direction,
        "accepted": accepted,
        "manifest": manifest,
        "summary": summary,
        "items": items,
        "content_address": DIFF_PREFIX + ":pending",
    }
    provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff(**body)
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff(**(body | {"content_address": address_diff(provisional)}))


def verify_diff(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff):
        raise ValidationError("runtime registry history diff verification requires a typed diff")
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff.from_mapping(value.to_dict())


def diff_from_mapping(value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff:
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff.from_mapping(value)


def diff_json(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> str:
    value = verify_diff(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ITEM_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ITEM_FIELDS) for item in value.items)
    return output.getvalue()


def render_diff_markdown(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> str:
    value = verify_diff(value)
    lines = [
        "# History-diff archive-transfer recovery-execution runtime-registry history diff",
        "",
        f"- Diff: {value.diff_id}",
        f"- Baseline: {value.left_history_id} ({value.left_history_address})",
        f"- Candidate: {value.right_history_id} ({value.right_history_address})",
        f"- Direction: {value.direction}",
        f"- Accepted: {value.accepted}",
        f"- Address: {value.content_address}",
        "",
        "| # | identity | change | changed fields | baseline | candidate |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {item.ordinal} | {item.identity} | {item.change} | {', '.join(item.changed_fields) or '—'} | {item.left_entry_address or '—'} | {item.right_entry_address or '—'} |" for item in value.items)
    return "\n".join(lines) + "\n"


def items_json(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItems) -> str:
    return canonical_json(HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItems.from_mapping(value.to_dict()).to_dict())


def summary_json(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary) -> str:
    return canonical_json(HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary.from_mapping(value.to_dict()).to_dict())


def manifest_json(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest) -> str:
    return canonical_json(HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest.from_mapping(value.to_dict()).to_dict())


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_diff(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_diff(value)
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("runtime registry history diff destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".federation-runtime-registry-history-diff-", dir=str(destination.parent)))
    try:
        items = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItems(value.items, address_items(value.items))
        documents = {"manifest.json": value.manifest.to_dict(), "diff.json": value.to_dict(), "items.json": items.to_dict(), "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("runtime registry history diff destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("runtime registry history diff artifact is not valid JSON") from error
    return _mapping(value, "runtime registry history diff artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError("runtime registry history diff artifact cannot be read") from error
    if actual != canonical_json(value):
        raise ValidationError("runtime registry history diff artifact is not canonical")


def load_diff(destination: str | Path) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff:
    destination = Path(destination)
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("runtime registry history diff source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)):
        raise ValidationError("runtime registry history diff directory must contain the exact file set")
    if any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("runtime registry history diff directory may contain only regular files")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        _read_canonical(destination / name, document)
        if len(canonical_json(document).encode("utf-8")) > MAX_DIFF_BYTES:
            raise ValidationError("runtime registry history diff artifact exceeds its size bound")
    value = diff_from_mapping(documents["diff.json"])
    manifest = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffManifest.from_mapping(documents["manifest.json"])
    items = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffItems.from_mapping(documents["items.json"])
    summary = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffSummary.from_mapping(documents["summary.json"])
    expected_items = {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)}
    if manifest.to_dict() != value.manifest.to_dict() or items.to_dict() != expected_items or summary.to_dict() != value.summary.to_dict():
        raise ValidationError("runtime registry history diff component documents do not replay diff.json")
    if tuple(manifest.artifact_addresses) != (items.content_address, summary.content_address):
        raise ValidationError("runtime registry history diff manifest artifact addresses do not replay")
    return value


def run_diff(left: history_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory, right: history_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory, *, diff_id: str = DEFAULT_DIFF_ID, destination: str | Path | None = None, overwrite: bool = False) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff:
    value = build_diff(left, right, diff_id=diff_id)
    if destination is not None:
        persist_diff(value, destination, overwrite=overwrite)
    return value


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryItem", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "identity": {"type": "string"}, "change": {"enum": list(CHANGES)}, "changed_fields": {"type": "array", "items": {"type": "string"}}, "left_entry_address": {"type": "string"}, "right_entry_address": {"type": "string"}, "left_snapshot": {"type": "object"}, "right_snapshot": {"type": "object"}, "content_address": {"type": "string"}}}


def items_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryItems", "type": "object", "additionalProperties": False, "required": list(ITEMS_FIELDS), "properties": {"items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"diff_id": {"type": "string"}, "left_history_id": {"type": "string"}, "right_history_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistorySummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"diff_id": {"type": "string"}, "left_history_id": {"type": "string"}, "right_history_id": {"type": "string"}, "left_history_address": {"type": "string"}, "right_history_address": {"type": "string"}, "left_entry_count": {"type": "integer", "minimum": 0}, "right_entry_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "direction": {"enum": list(DIRECTIONS)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "left_history_id": {"type": "string"}, "right_history_id": {"type": "string"}, "left_history_address": {"type": "string"}, "right_history_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "direction": {"enum": list(DIRECTIONS)}, "accepted": {"type": "boolean"}, "manifest": manifest_schema(), "summary": summary_schema(), "items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_id_prefix": DIFF_PREFIX, "item_id_prefix": ITEM_PREFIX, "files": list(FILES), "changes": list(CHANGES), "directions": list(DIRECTIONS), "max_items": MAX_ITEMS, "max_diff_bytes": MAX_DIFF_BYTES, "operations": ["build", "verify", "persist", "load", "csv", "markdown", "schema", "capabilities"]}
