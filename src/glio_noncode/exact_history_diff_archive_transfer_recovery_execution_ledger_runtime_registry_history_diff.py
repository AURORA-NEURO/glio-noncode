"""Deterministic baseline/candidate diff for execution-ledger runtime registry histories."""

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

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = history_model.VERSION + "-diff-v1"
BOUNDARY = history_model.BOUNDARY + "_diff"
DIFF_PREFIX = history_model.HISTORY_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
ITEMS_PREFIX = DIFF_PREFIX + "-items"
ARTIFACT_PREFIX = DIFF_PREFIX + "-artifact"
MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
SUMMARY_PREFIX = DIFF_PREFIX + "-summary"
DEFAULT_DIFF_ID = DIFF_PREFIX
FILES = ("manifest.json", "diff.json", "items.json", "summary.json")
ARTIFACT_FILES = ("items.json", "summary.json")
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "changed", "unchanged")
MAX_ITEMS = history_model.MAX_ENTRIES * 2
MAX_DIFF_BYTES = 16 * 1024 * 1024
ITEM_FIELDS = ("ordinal", "identity", "change", "changed_fields", "left_entry_address", "right_entry_address", "left_snapshot", "right_snapshot", "content_address")
ITEMS_FIELDS = ("items", "content_address")
ARTIFACT_FIELDS = ("ordinal", "name", "size", "hash", "content_address")
MANIFEST_FIELDS = ("diff_id", "registry_id", "left_history_id", "right_history_id", "version", "boundary", "files", "artifacts", "manifest_address")
SUMMARY_FIELDS = ("diff_id", "registry_id", "left_history_id", "right_history_id", "left_history_address", "right_history_address", "left_entry_count", "right_entry_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "accepted", "content_address")
DIFF_FIELDS = ("diff_id", "registry_id", "version", "boundary", "left_history_id", "right_history_id", "left_history_address", "right_history_address", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "accepted", "manifest", "summary", "items", "content_address")


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
    return history_model._public(value)


def _snapshot(value: Any, field: str, *, required: bool) -> dict[str, Any]:
    if value is None and not required:
        return {}
    value = _mapping(value, field)
    if len(canonical_bytes(value)) > 32768:
        raise ValidationError(f"{field} is too large")
    if not _public(value):
        raise ValidationError(f"{field} crosses the public boundary")
    return dict(value)


def _quality(value: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> tuple[int, int, int, int, int, int]:
    ranks = {"ready": 0, "empty": 1, "blocked": 2}
    return (ranks[value.state], -value.latest_ready_count, -value.latest_accepted_count, value.latest_blocked_count, -value.latest_entry_count, value.entry_count)


def _direction(left: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory, right: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory, item_change: bool) -> str:
    if _quality(right) < _quality(left):
        return "improved"
    if _quality(right) > _quality(left):
        return "regressed"
    return "changed" if item_change else "unchanged"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem:
    """One stable-ordinal comparison with two-sided public evidence."""

    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, identity: str, change: str, changed_fields: Sequence[str], left_entry_address: str, right_entry_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history diff item ordinal", MAX_ITEMS, lower=1)
        self.identity = _label(identity, "registry history diff item identity")
        if change not in CHANGES:
            raise ValidationError("registry history diff item change is unsupported")
        self.change = change
        fields = tuple(_label(item, "registry history diff changed field") for item in _sequence(changed_fields, "registry history diff changed fields", len(history_model.ENTRY_FIELDS)))
        allowed = tuple(field for field in history_model.ENTRY_FIELDS if field != "content_address")
        if len(fields) != len(set(fields)) or any(field not in allowed for field in fields) or fields != tuple(field for field in allowed if field in fields):
            raise ValidationError("registry history diff changed fields must be unique and preserve contract order")
        self.changed_fields = fields
        self.left_entry_address = _address(left_entry_address, "registry history diff left entry address", history_model.ENTRY_PREFIX, required=False)
        self.right_entry_address = _address(right_entry_address, "registry history diff right entry address", history_model.ENTRY_PREFIX, required=False)
        self.left_snapshot = _snapshot(left_snapshot, "registry history diff left snapshot", required=False)
        self.right_snapshot = _snapshot(right_snapshot, "registry history diff right snapshot", required=False)
        self.content_address = _address(content_address, "registry history diff item address", ITEM_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.left_snapshot or self.left_entry_address or not self.right_snapshot or not self.right_entry_address):
            raise ValidationError("added diff items require only a candidate snapshot")
        if self.change == "removed" and (not self.left_snapshot or not self.left_entry_address or self.right_snapshot or self.right_entry_address):
            raise ValidationError("removed diff items require only a baseline snapshot")
        if self.change in ("changed", "unchanged") and (not self.left_snapshot or not self.right_snapshot or not self.left_entry_address or not self.right_entry_address):
            raise ValidationError("paired diff items require both snapshots")
        if self.change == "unchanged" and (self.changed_fields or self.left_snapshot != self.right_snapshot):
            raise ValidationError("unchanged diff items must have equal snapshots")
        if self.change == "changed" and (not self.changed_fields or self.left_snapshot == self.right_snapshot):
            raise ValidationError("changed diff items require field deltas")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff item crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("registry history diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff item")
        _strict(value, set(cls.FIELDS), "registry history diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem):
        raise ValidationError("registry history diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItems:
    FIELDS = ITEMS_FIELDS

    def __init__(self, items: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.items = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem.from_mapping(item) for item in _sequence(items, "registry history diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "registry history diff items address", ITEMS_PREFIX, allow_pending=True)
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            raise ValidationError("registry history diff item ordinals must be contiguous")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff items cross the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_items(self.items) != self.content_address:
            raise ValidationError("registry history diff items address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff items")
        _strict(value, set(cls.FIELDS), "registry history diff items")
        return cls(value["items"], value["content_address"])


def address_items(value: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem) for item in typed):
        raise ValidationError("registry history diff items address requires typed items")
    return content_hash([item.to_dict() for item in typed], prefix=ITEMS_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArtifact:
    FIELDS = ARTIFACT_FIELDS

    def __init__(self, ordinal: int, name: str, size: int, hash: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history diff artifact ordinal", len(ARTIFACT_FILES), lower=1)
        self.name = _label(name, "registry history diff artifact name")
        if self.name not in ARTIFACT_FILES:
            raise ValidationError("registry history diff artifact name is unsupported")
        self.size = _count(size, "registry history diff artifact size", MAX_DIFF_BYTES, lower=1)
        self.hash = _address(hash, "registry history diff artifact hash", ARTIFACT_PREFIX)
        self.content_address = _address(content_address, "registry history diff artifact content address", required=True)
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff artifact crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff artifact")
        _strict(value, set(cls.FIELDS), "registry history diff artifact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_artifact(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArtifact) -> str:
    return content_hash(value.to_dict(), prefix=ARTIFACT_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, diff_id: str, registry_id: str, left_history_id: str, right_history_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArtifact], manifest_address: str) -> None:
        self.diff_id = _label(diff_id, "registry history diff ID")
        self.registry_id = _label(registry_id, "registry history diff registry ID")
        self.left_history_id = _label(left_history_id, "registry history diff baseline ID")
        self.right_history_id = _label(right_history_id, "registry history diff candidate ID")
        self.version = _text(version, "registry history diff version", 1024)
        self.boundary = _text(boundary, "registry history diff boundary", 1024)
        self.files = tuple(_label(item, "registry history diff manifest file") for item in _sequence(files, "registry history diff manifest files", len(FILES)))
        self.artifacts = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArtifact) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArtifact.from_mapping(item) for item in _sequence(artifacts, "registry history diff manifest artifacts", len(ARTIFACT_FILES)))
        self.manifest_address = _address(manifest_address, "registry history diff manifest address", MANIFEST_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.files != FILES or tuple(item.name for item in self.artifacts) != ARTIFACT_FILES or tuple(item.ordinal for item in self.artifacts) != (1, 2):
            raise ValidationError("registry history diff manifest contract does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff manifest crosses the public boundary")
        if not self.manifest_address.startswith("pending:") and not self.manifest_address.endswith(":pending") and address_manifest(self) != self.manifest_address:
            raise ValidationError("registry history diff manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "registry_id": self.registry_id, "left_history_id": self.left_history_id, "right_history_id": self.right_history_id, "version": self.version, "boundary": self.boundary, "files": self.files, "artifacts": [item.to_dict() for item in self.artifacts], "manifest_address": self.manifest_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff manifest")
        _strict(value, set(cls.FIELDS), "registry history diff manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest) -> str:
    return content_hash(value.to_dict() | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, diff_id: str, registry_id: str, left_history_id: str, right_history_id: str, left_history_address: str, right_history_address: str, left_entry_count: int, right_entry_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "registry history diff summary ID")
        self.registry_id = _label(registry_id, "registry history diff summary registry ID")
        self.left_history_id = _label(left_history_id, "registry history diff summary baseline ID")
        self.right_history_id = _label(right_history_id, "registry history diff summary candidate ID")
        self.left_history_address = _address(left_history_address, "registry history diff summary baseline address", history_model.HISTORY_PREFIX)
        self.right_history_address = _address(right_history_address, "registry history diff summary candidate address", history_model.HISTORY_PREFIX)
        self.left_entry_count = _count(left_entry_count, "registry history diff baseline entry count", history_model.MAX_ENTRIES)
        self.right_entry_count = _count(right_entry_count, "registry history diff candidate entry count", history_model.MAX_ENTRIES)
        self.added_count = _count(added_count, "registry history diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "registry history diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "registry history diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "registry history diff unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS:
            raise ValidationError("registry history diff direction is unsupported")
        self.direction = direction
        self.accepted = _bool(accepted, "registry history diff acceptance")
        self.content_address = _address(content_address, "registry history diff summary address", SUMMARY_PREFIX, allow_pending=True)
        if self.added_count + self.removed_count + self.changed_count + self.unchanged_count > MAX_ITEMS or not _public(self.to_dict()):
            raise ValidationError("registry history diff summary is invalid")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("registry history diff summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff summary")
        _strict(value, set(cls.FIELDS), "registry history diff summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff:
    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, registry_id: str, version: str, boundary: str, left_history_id: str, right_history_id: str, left_history_address: str, right_history_address: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, accepted: bool, manifest: Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest, summary: Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary, items: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem], content_address: str) -> None:
        self.diff_id = _label(diff_id, "registry history diff ID")
        self.registry_id = _label(registry_id, "registry history diff registry ID")
        self.version = _text(version, "registry history diff version", 1024)
        self.boundary = _text(boundary, "registry history diff boundary", 1024)
        self.left_history_id = _label(left_history_id, "registry history diff baseline ID")
        self.right_history_id = _label(right_history_id, "registry history diff candidate ID")
        self.left_history_address = _address(left_history_address, "registry history diff baseline address", history_model.HISTORY_PREFIX)
        self.right_history_address = _address(right_history_address, "registry history diff candidate address", history_model.HISTORY_PREFIX)
        self.item_count = _count(item_count, "registry history diff item count", MAX_ITEMS)
        self.added_count = _count(added_count, "registry history diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "registry history diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "registry history diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "registry history diff unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS:
            raise ValidationError("registry history diff direction is unsupported")
        self.direction = direction
        self.accepted = _bool(accepted, "registry history diff acceptance")
        self.manifest = manifest if isinstance(manifest, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary.from_mapping(summary)
        self.items = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem.from_mapping(item) for item in _sequence(items, "registry history diff item list", MAX_ITEMS))
        self.content_address = _address(content_address, "registry history diff address", DIFF_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.item_count != len(self.items) or tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            raise ValidationError("registry history diff does not replay its ordered items")
        counts = {change: sum(item.change == change for item in self.items) for change in CHANGES}
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != tuple(counts[item] for item in ("added", "removed", "changed", "unchanged")):
            raise ValidationError("registry history diff counts do not replay")
        if (self.manifest.diff_id, self.manifest.registry_id, self.manifest.left_history_id, self.manifest.right_history_id) != (self.diff_id, self.registry_id, self.left_history_id, self.right_history_id):
            raise ValidationError("registry history diff manifest linkage does not replay")
        if (self.summary.diff_id, self.summary.registry_id, self.summary.left_history_id, self.summary.right_history_id, self.summary.left_history_address, self.summary.right_history_address, self.summary.left_entry_count, self.summary.right_entry_count) != (self.diff_id, self.registry_id, self.left_history_id, self.right_history_id, self.left_history_address, self.right_history_address, self._left_count(), self._right_count()):
            raise ValidationError("registry history diff summary linkage does not replay")
        if self.summary.direction != self.direction or self.summary.accepted != self.accepted:
            raise ValidationError("registry history diff summary decision does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("registry history diff address does not replay")

    def _left_count(self) -> int:
        return self.summary.left_entry_count

    def _right_count(self) -> int:
        return self.summary.right_entry_count

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "left_history_id": self.left_history_id, "right_history_id": self.right_history_id, "left_history_address": self.left_history_address, "right_history_address": self.right_history_address, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "direction": self.direction, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "items": [item.to_dict() for item in self.items], "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "summary", "items"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff")
        _strict(value, set(cls.FIELDS), "registry history diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _identity(ordinal: int) -> str:
    return f"ordinal-{ordinal:08d}"


def _changed_fields(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(field for field in history_model.ENTRY_FIELDS if field != "content_address" and left.get(field) != right.get(field))


def _item(ordinal: int, left: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry | None, right: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry | None):
    if left is None and right is None:
        raise ValidationError("registry history diff item requires a baseline or candidate")
    if left is None:
        change, left_address, right_address, left_snapshot, right_snapshot, changed = "added", "", right.content_address, {}, right.to_dict(), ()
    elif right is None:
        change, left_address, right_address, left_snapshot, right_snapshot, changed = "removed", left.content_address, "", left.to_dict(), {}, ()
    else:
        left_snapshot, right_snapshot = left.to_dict(), right.to_dict()
        changed = _changed_fields(left_snapshot, right_snapshot)
        change = "changed" if changed else "unchanged"
        left_address, right_address = left.content_address, right.content_address
    body = {"ordinal": ordinal, "identity": _identity(ordinal), "change": change, "changed_fields": changed, "left_entry_address": left_address, "right_entry_address": right_address, "left_snapshot": left_snapshot, "right_snapshot": right_snapshot, "content_address": ITEM_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem(**(body | {"content_address": address_item(provisional)}))


def _artifact(ordinal: int, name: str, body: Mapping[str, Any], content_address: str):
    payload = canonical_bytes(body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArtifact(ordinal, name, len(payload), hash_bytes(payload, prefix=ARTIFACT_PREFIX), content_address)


def build_diff(left: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory, right: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory, *, diff_id: str = DEFAULT_DIFF_ID):
    left, right = history_model.verify_history(left), history_model.verify_history(right)
    if left.registry_id != right.registry_id:
        raise ValidationError("registry history diffs require one registry identity")
    items = tuple(_item(ordinal, left.entries[ordinal - 1] if ordinal <= left.entry_count else None, right.entries[ordinal - 1] if ordinal <= right.entry_count else None) for ordinal in range(1, max(left.entry_count, right.entry_count) + 1))
    counts = {change: sum(item.change == change for item in items) for change in CHANGES}
    direction = _direction(left, right, any(item.change != "unchanged" for item in items))
    accepted = left.accepted and right.accepted
    items_projection = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItems(items, address_items(items))
    summary_body = {"diff_id": diff_id, "registry_id": left.registry_id, "left_history_id": left.history_id, "right_history_id": right.history_id, "left_history_address": left.content_address, "right_history_address": right.content_address, "left_entry_count": left.entry_count, "right_entry_count": right.entry_count, "added_count": counts["added"], "removed_count": counts["removed"], "changed_count": counts["changed"], "unchanged_count": counts["unchanged"], "direction": direction, "accepted": accepted, "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary(**summary_body)
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    items_body, summary_body_final = items_projection.to_dict(), summary.to_dict()
    artifacts = (_artifact(1, "items.json", items_body, items_projection.content_address), _artifact(2, "summary.json", summary_body_final, summary.content_address))
    manifest_body = {"diff_id": diff_id, "registry_id": left.registry_id, "left_history_id": left.history_id, "right_history_id": right.history_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": artifacts, "manifest_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest(**manifest_body)
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest(**(manifest_body | {"manifest_address": address_manifest(manifest_provisional)}))
    diff_body = {"diff_id": diff_id, "registry_id": left.registry_id, "version": VERSION, "boundary": BOUNDARY, "left_history_id": left.history_id, "right_history_id": right.history_id, "left_history_address": left.content_address, "right_history_address": right.content_address, "item_count": len(items), "added_count": counts["added"], "removed_count": counts["removed"], "changed_count": counts["changed"], "unchanged_count": counts["unchanged"], "direction": direction, "accepted": accepted, "manifest": manifest, "summary": summary, "items": items, "content_address": DIFF_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff(**diff_body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff(**(diff_body | {"content_address": address_diff(provisional)}))


def verify_diff(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff):
        raise ValidationError("registry history diff verification requires a typed diff")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff.from_mapping(value.to_dict())


def diff_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff.from_mapping(value)


def diff_json(value) -> str:
    return canonical_json(verify_diff(value).to_dict())


def items_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItems) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItems.from_mapping(value.to_dict()).to_dict())


def summary_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary.from_mapping(value.to_dict()).to_dict())


def manifest_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest) -> str:
    return canonical_json(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest.from_mapping(value.to_dict()).to_dict())


def diff_csv(value) -> str:
    value = verify_diff(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ITEM_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ITEM_FIELDS) for item in value.items)
    return output.getvalue()


def render_diff_markdown(value) -> str:
    value = verify_diff(value)
    lines = ["# Execution-ledger runtime registry history diff", "", f"- Diff: {value.diff_id}", f"- Registry: {value.registry_id}", f"- Baseline: {value.left_history_id} ({value.left_history_address})", f"- Candidate: {value.right_history_id} ({value.right_history_address})", f"- Direction: {value.direction}", f"- Accepted: {value.accepted}", f"- Address: {value.content_address}", "", "| # | change | changed fields | baseline | candidate |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.change} | {', '.join(item.changed_fields) or '—'} | {item.left_entry_address or '—'} | {item.right_entry_address or '—'} |" for item in value.items)
    return "\n".join(lines) + "\n"


def _documents(value) -> dict[str, bytes]:
    value = verify_diff(value)
    return {"manifest.json": canonical_bytes(value.manifest.to_dict()), "diff.json": canonical_bytes(value.to_dict()), "items.json": canonical_bytes(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItems(value.items, address_items(value.items)).to_dict()), "summary.json": canonical_bytes(value.summary.to_dict())}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_diff(value, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_diff(value)
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("registry history diff destination exists or is not a directory")
    documents = _documents(value)
    for name, receipt in zip(ARTIFACT_FILES, value.manifest.artifacts):
        if len(documents[name]) != receipt.size or hash_bytes(documents[name], prefix=ARTIFACT_PREFIX) != receipt.hash:
            raise ValidationError("registry history diff artifact receipt does not replay")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".execution-ledger-registry-history-diff-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (temporary / name).write_bytes(documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("registry history diff destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("registry history diff artifact is not valid JSON") from error
    return _mapping(value, "registry history diff artifact")


def load_diff(destination: str | Path):
    destination = Path(destination)
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("registry history diff source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("registry history diff directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        actual = (destination / name).read_text(encoding="utf-8")
        if actual != canonical_json(document) or len(canonical_bytes(document)) > MAX_DIFF_BYTES:
            raise ValidationError("registry history diff artifact is not canonical or exceeds its bound")
    value = diff_from_mapping(documents["diff.json"])
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest.from_mapping(documents["manifest.json"])
    items = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItems.from_mapping(documents["items.json"])
    summary = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary.from_mapping(documents["summary.json"])
    if manifest.to_dict() != value.manifest.to_dict() or items.to_dict() != {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)} or summary.to_dict() != value.summary.to_dict():
        raise ValidationError("registry history diff component documents do not replay diff.json")
    for name, receipt in zip(ARTIFACT_FILES, manifest.artifacts):
        payload = (destination / name).read_bytes()
        if len(payload) != receipt.size or hash_bytes(payload, prefix=ARTIFACT_PREFIX) != receipt.hash:
            raise ValidationError("registry history diff artifact byte receipt does not replay")
    return value


def run_diff(left, right, *, diff_id: str = DEFAULT_DIFF_ID, destination: str | Path | None = None, overwrite: bool = False):
    value = build_diff(left, right, diff_id=diff_id)
    if destination is not None:
        persist_diff(value, destination, overwrite=overwrite)
    return value


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffItem", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "identity": {"type": "string"}, "change": {"enum": list(CHANGES)}, "changed_fields": {"type": "array", "items": {"type": "string"}}, "left_entry_address": {"type": "string"}, "right_entry_address": {"type": "string"}, "left_snapshot": {"type": "object"}, "right_snapshot": {"type": "object"}, "content_address": {"type": "string"}}}


def items_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffItems", "type": "object", "additionalProperties": False, "required": list(ITEMS_FIELDS), "properties": {"items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string"}}}


def artifact_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArtifact", "type": "object", "additionalProperties": False, "required": list(ARTIFACT_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": len(ARTIFACT_FILES)}, "name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string"}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"diff_id": {"type": "string"}, "registry_id": {"type": "string"}, "left_history_id": {"type": "string"}, "right_history_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": artifact_schema(), "minItems": 2, "maxItems": 2}, "manifest_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"diff_id": {"type": "string"}, "registry_id": {"type": "string"}, "left_history_id": {"type": "string"}, "right_history_id": {"type": "string"}, "left_history_address": {"type": "string"}, "right_history_address": {"type": "string"}, "left_entry_count": {"type": "integer", "minimum": 0}, "right_entry_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "direction": {"enum": list(DIRECTIONS)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {"diff_id": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "left_history_id": {"type": "string"}, "right_history_id": {"type": "string"}, "left_history_address": {"type": "string"}, "right_history_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "direction": {"enum": list(DIRECTIONS)}, "accepted": {"type": "boolean"}, "manifest": manifest_schema(), "summary": summary_schema(), "items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "items_prefix": ITEMS_PREFIX, "artifact_prefix": ARTIFACT_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "summary_prefix": SUMMARY_PREFIX, "files": FILES, "artifact_files": ARTIFACT_FILES, "changes": CHANGES, "directions": DIRECTIONS, "max_items": MAX_ITEMS, "max_diff_bytes": MAX_DIFF_BYTES, "operations": ("build_diff", "verify_diff", "diff_from_mapping", "persist_diff", "load_diff", "run_diff", "diff_json", "diff_csv", "render_diff_markdown", "items_json", "summary_json", "manifest_json"), "features": ("same-registry baseline/candidate comparison", "stable ordinal matching", "field-level change evidence", "two-sided addressed snapshots", "directional quality replay", "exact four-file atomic persistence", "manifest byte receipts", "canonical reload verification"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["VERSION", "BOUNDARY", "DIFF_PREFIX", "ITEM_PREFIX", "ITEMS_PREFIX", "ARTIFACT_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_DIFF_ID", "FILES", "ARTIFACT_FILES", "CHANGES", "DIRECTIONS", "MAX_ITEMS", "MAX_DIFF_BYTES", "ITEM_FIELDS", "ITEMS_FIELDS", "ARTIFACT_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "DIFF_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItems", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArtifact", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffManifest", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffSummary", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff", "address_item", "address_items", "address_artifact", "address_manifest", "address_summary", "address_diff", "build_diff", "verify_diff", "diff_from_mapping", "diff_json", "diff_csv", "render_diff_markdown", "items_json", "summary_json", "manifest_json", "persist_diff", "load_diff", "run_diff", "item_schema", "items_schema", "artifact_schema", "manifest_schema", "summary_schema", "diff_schema", "capabilities"]
