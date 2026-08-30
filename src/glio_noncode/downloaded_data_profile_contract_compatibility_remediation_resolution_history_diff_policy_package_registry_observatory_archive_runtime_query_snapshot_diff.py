"""Deterministic structural diffs between persisted runtime-query snapshots.

The diff is intentionally value-free. It compares public runtime-query rows by
stable resource/stage/component/name identity, preserves the two row receipts,
and records only structural change evidence. The handoff can be persisted and
replayed without reopening either source archive.
"""

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

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot as snapshot_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = snapshot_model.VERSION + "-diff-v1"
BOUNDARY = snapshot_model.BOUNDARY + "_diff"
DIFF_PREFIX = snapshot_model.SNAPSHOT_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
ITEMS_PREFIX = DIFF_PREFIX + "-items"
MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
SUMMARY_PREFIX = DIFF_PREFIX + "-summary"
DEFAULT_DIFF_ID = "policy-package-registry-observatory-archive-runtime-query-snapshot-diff"
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "mixed", "unchanged")
FILES = ("manifest.json", "diff.json", "items.json", "summary.json")
MANIFEST_ARTIFACT_FILES = ("items.json", "summary.json")
MAX_ITEMS = snapshot_model.query_model.MAX_TOTAL_COUNT * 2
SEMANTIC_ROW_FIELDS = tuple(field for field in snapshot_model.query_model.ROW_FIELDS if field != "content_address")
ITEM_FIELDS = ("ordinal", "identity", "resource", "stage", "component", "name", "change", "left_row_address", "right_row_address", "left_row", "right_row", "changed_fields", "content_address")
ITEMS_FIELDS = ("items", "content_address")
MANIFEST_FIELDS = ("diff_id", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("diff_id", "left_snapshot_id", "right_snapshot_id", "left_snapshot_address", "right_snapshot_address", "left_runtime_id", "right_runtime_id", "left_query_address", "right_query_address", "left_row_count", "right_row_count", "added_count", "removed_count", "changed_count", "unchanged_count", "left_accepted", "right_accepted", "left_state", "right_state", "direction", "state_transition", "changed_field_count", "content_address")
DIFF_FIELDS = ("diff_id", "version", "boundary", "left_snapshot_id", "right_snapshot_id", "left_snapshot_address", "right_snapshot_address", "left_runtime_id", "right_runtime_id", "left_query_address", "right_query_address", "left_row_count", "right_row_count", "added_count", "removed_count", "changed_count", "unchanged_count", "left_accepted", "right_accepted", "left_state", "right_state", "direction", "state_transition", "changed_field_count", "manifest", "summary", "items", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _snapshot_row(value: Any, field: str) -> dict[str, Any]:
    value = _mapping(value, field)
    if not value:
        return {}
    _strict(value, set(snapshot_model.query_model.ROW_FIELDS), field)
    return dict(value)


def _identity(row: Mapping[str, Any]) -> str:
    return "|".join(str(row[field]) for field in ("resource", "stage", "component", "name"))


def _semantic(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(row[field] for field in SEMANTIC_ROW_FIELDS)


def _changed_fields(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[str, ...]:
    if not left:
        return SEMANTIC_ROW_FIELDS if right else ()
    if not right:
        return SEMANTIC_ROW_FIELDS
    return tuple(field for field in SEMANTIC_ROW_FIELDS if left[field] != right[field])


def _direction(left_accepted: bool, right_accepted: bool, changed: bool) -> str:
    if not left_accepted and right_accepted:
        return "improved"
    if left_accepted and not right_accepted:
        return "regressed"
    return "mixed" if changed else "unchanged"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem:
    """One stable-identity row comparison between two snapshots."""

    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, identity: str, resource: str, stage: str, component: str, name: str, change: str, left_row_address: str, right_row_address: str, left_row: Mapping[str, Any], right_row: Mapping[str, Any], changed_fields: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "snapshot diff item ordinal", MAX_ITEMS, positive=True)
        self.identity = _text(identity, "snapshot diff item identity", 1024, required=True)
        self.resource = _label(resource, "snapshot diff item resource", required=True)
        self.stage = _label(stage, "snapshot diff item stage")
        self.component = _label(component, "snapshot diff item component")
        self.name = _label(name, "snapshot diff item name")
        self.change = _label(change, "snapshot diff item change", required=True)
        if self.change not in CHANGES:
            raise ValidationError("snapshot diff item change is unsupported")
        self.left_row_address = _address(left_row_address, "snapshot diff left row address", snapshot_model.query_model.ROW_PREFIX, required=False)
        self.right_row_address = _address(right_row_address, "snapshot diff right row address", snapshot_model.query_model.ROW_PREFIX, required=False)
        self.left_row = _snapshot_row(left_row, "snapshot diff left row")
        self.right_row = _snapshot_row(right_row, "snapshot diff right row")
        self.changed_fields = tuple(_label(item, "snapshot diff changed field", required=True) for item in _sequence(changed_fields, "snapshot diff changed fields", len(SEMANTIC_ROW_FIELDS)))
        if len(set(self.changed_fields)) != len(self.changed_fields) or any(item not in SEMANTIC_ROW_FIELDS for item in self.changed_fields):
            raise ValidationError("snapshot diff changed fields are invalid")
        self.content_address = _address(content_address, "snapshot diff item address", ITEM_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.identity != _identity(self.left_row or self.right_row):
            raise ValidationError("snapshot diff item identity does not replay")
        if self.resource != (self.left_row or self.right_row)["resource"] or self.stage != (self.left_row or self.right_row)["stage"] or self.component != (self.left_row or self.right_row)["component"] or self.name != (self.left_row or self.right_row)["name"]:
            raise ValidationError("snapshot diff item identity fields do not replay")
        if self.left_row and self.left_row_address != self.left_row["content_address"] or not self.left_row and self.left_row_address:
            raise ValidationError("snapshot diff left row address does not replay")
        if self.right_row and self.right_row_address != self.right_row["content_address"] or not self.right_row and self.right_row_address:
            raise ValidationError("snapshot diff right row address does not replay")
        if self.change == "added" and (self.left_row or not self.right_row):
            raise ValidationError("added snapshot diff item does not have one right row")
        if self.change == "removed" and (not self.left_row or self.right_row):
            raise ValidationError("removed snapshot diff item does not have one left row")
        if self.change in {"changed", "unchanged"} and (not self.left_row or not self.right_row):
            raise ValidationError("paired snapshot diff item does not have two rows")
        if self.change == "unchanged" and _semantic(self.left_row) != _semantic(self.right_row):
            raise ValidationError("unchanged snapshot diff item contains a semantic difference")
        if self.change == "changed" and _semantic(self.left_row) == _semantic(self.right_row):
            raise ValidationError("changed snapshot diff item contains no semantic difference")
        if self.changed_fields != _changed_fields(self.left_row, self.right_row):
            raise ValidationError("snapshot diff changed fields do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("snapshot diff item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("snapshot diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot diff item")
        _strict(value, set(cls.FIELDS), "snapshot diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem):
        raise ValidationError("snapshot diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


def address_items(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem) for item in typed):
        raise ValidationError("snapshot diff items address requires typed items")
    return content_hash({"items": [item.to_dict() for item in typed]}, prefix=ITEMS_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, diff_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.diff_id = _label(diff_id, "snapshot diff manifest diff ID", required=True)
        self.files = tuple(_label(item, "snapshot diff manifest file", required=True) for item in _sequence(files, "snapshot diff manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "snapshot diff manifest artifact address", required=True) for item in _sequence(artifact_addresses, "snapshot diff manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "snapshot diff manifest address", MANIFEST_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("snapshot diff manifest does not close the public file boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("snapshot diff manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot diff manifest")
        _strict(value, set(cls.FIELDS), "snapshot diff manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest):
        raise ValidationError("snapshot diff manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, diff_id: str, left_snapshot_id: str, right_snapshot_id: str, left_snapshot_address: str, right_snapshot_address: str, left_runtime_id: str, right_runtime_id: str, left_query_address: str, right_query_address: str, left_row_count: int, right_row_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, left_accepted: bool, right_accepted: bool, left_state: str, right_state: str, direction: str, state_transition: str, changed_field_count: int, content_address: str) -> None:
        self.diff_id = _label(diff_id, "snapshot diff summary diff ID", required=True)
        self.left_snapshot_id = _label(left_snapshot_id, "snapshot diff summary left snapshot ID", required=True)
        self.right_snapshot_id = _label(right_snapshot_id, "snapshot diff summary right snapshot ID", required=True)
        self.left_snapshot_address = _address(left_snapshot_address, "snapshot diff summary left snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=True)
        self.right_snapshot_address = _address(right_snapshot_address, "snapshot diff summary right snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=True)
        self.left_runtime_id = _label(left_runtime_id, "snapshot diff summary left runtime ID", required=True)
        self.right_runtime_id = _label(right_runtime_id, "snapshot diff summary right runtime ID", required=True)
        self.left_query_address = _address(left_query_address, "snapshot diff summary left query address", snapshot_model.query_model.QUERY_PREFIX, required=True)
        self.right_query_address = _address(right_query_address, "snapshot diff summary right query address", snapshot_model.query_model.QUERY_PREFIX, required=True)
        self.left_row_count = _count(left_row_count, "snapshot diff summary left row count", MAX_ITEMS)
        self.right_row_count = _count(right_row_count, "snapshot diff summary right row count", MAX_ITEMS)
        self.added_count = _count(added_count, "snapshot diff summary added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "snapshot diff summary removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "snapshot diff summary changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "snapshot diff summary unchanged count", MAX_ITEMS)
        self.left_accepted = _bool(left_accepted, "snapshot diff summary left acceptance")
        self.right_accepted = _bool(right_accepted, "snapshot diff summary right acceptance")
        self.left_state = _label(left_state, "snapshot diff summary left state", required=True)
        self.right_state = _label(right_state, "snapshot diff summary right state", required=True)
        if self.left_state not in snapshot_model.STATES or self.right_state not in snapshot_model.STATES:
            raise ValidationError("snapshot diff summary state is unsupported")
        self.direction = _label(direction, "snapshot diff summary direction", required=True)
        if self.direction not in DIRECTIONS:
            raise ValidationError("snapshot diff summary direction is unsupported")
        self.state_transition = _label(state_transition, "snapshot diff summary state transition", required=True)
        self.changed_field_count = _count(changed_field_count, "snapshot diff summary changed field count", MAX_ITEMS * len(SEMANTIC_ROW_FIELDS))
        self.content_address = _address(content_address, "snapshot diff summary address", SUMMARY_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.added_count + self.removed_count + self.changed_count + self.unchanged_count > MAX_ITEMS or self.changed_count == 0 and self.changed_field_count != 0:
            raise ValidationError("snapshot diff summary counts exceed their bounds")
        if not _public(self.to_dict()):
            raise ValidationError("snapshot diff summary crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("snapshot diff summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot diff summary")
        _strict(value, set(cls.FIELDS), "snapshot diff summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary):
        raise ValidationError("snapshot diff summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff:
    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, version: str, boundary: str, left_snapshot_id: str, right_snapshot_id: str, left_snapshot_address: str, right_snapshot_address: str, left_runtime_id: str, right_runtime_id: str, left_query_address: str, right_query_address: str, left_row_count: int, right_row_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, left_accepted: bool, right_accepted: bool, left_state: str, right_state: str, direction: str, state_transition: str, changed_field_count: int, manifest: Mapping[str, Any] | DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest, summary: Mapping[str, Any] | DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary, items: Sequence[Mapping[str, Any] | DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem], content_address: str) -> None:
        self.diff_id = _label(diff_id, "snapshot diff ID", required=True)
        self.version = _text(version, "snapshot diff version", 512, required=True)
        self.boundary = _text(boundary, "snapshot diff boundary", 512, required=True)
        self.left_snapshot_id = _label(left_snapshot_id, "snapshot diff left snapshot ID", required=True)
        self.right_snapshot_id = _label(right_snapshot_id, "snapshot diff right snapshot ID", required=True)
        self.left_snapshot_address = _address(left_snapshot_address, "snapshot diff left snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=True)
        self.right_snapshot_address = _address(right_snapshot_address, "snapshot diff right snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=True)
        self.left_runtime_id = _label(left_runtime_id, "snapshot diff left runtime ID", required=True)
        self.right_runtime_id = _label(right_runtime_id, "snapshot diff right runtime ID", required=True)
        self.left_query_address = _address(left_query_address, "snapshot diff left query address", snapshot_model.query_model.QUERY_PREFIX, required=True)
        self.right_query_address = _address(right_query_address, "snapshot diff right query address", snapshot_model.query_model.QUERY_PREFIX, required=True)
        self.left_row_count = _count(left_row_count, "snapshot diff left row count", MAX_ITEMS)
        self.right_row_count = _count(right_row_count, "snapshot diff right row count", MAX_ITEMS)
        self.added_count = _count(added_count, "snapshot diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "snapshot diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "snapshot diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "snapshot diff unchanged count", MAX_ITEMS)
        self.left_accepted = _bool(left_accepted, "snapshot diff left acceptance")
        self.right_accepted = _bool(right_accepted, "snapshot diff right acceptance")
        self.left_state = _label(left_state, "snapshot diff left state", required=True)
        self.right_state = _label(right_state, "snapshot diff right state", required=True)
        if self.left_state not in snapshot_model.STATES or self.right_state not in snapshot_model.STATES:
            raise ValidationError("snapshot diff state is unsupported")
        self.direction = _label(direction, "snapshot diff direction", required=True)
        if self.direction not in DIRECTIONS:
            raise ValidationError("snapshot diff direction is unsupported")
        self.state_transition = _label(state_transition, "snapshot diff state transition", required=True)
        self.changed_field_count = _count(changed_field_count, "snapshot diff changed field count", MAX_ITEMS * len(SEMANTIC_ROW_FIELDS))
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary.from_mapping(summary)
        self.items = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem.from_mapping(item) for item in _sequence(items, "snapshot diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "snapshot diff address", DIFF_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("snapshot diff version or boundary is not current")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or len({item.identity for item in self.items}) != len(self.items):
            raise ValidationError("snapshot diff item order or identity is not conserved")
        counts = tuple(sum(item.change == change for item in self.items) for change in CHANGES)
        if counts != (self.added_count, self.removed_count, self.changed_count, self.unchanged_count):
            raise ValidationError("snapshot diff item counts do not replay")
        if (sum(bool(item.left_row) for item in self.items), sum(bool(item.right_row) for item in self.items)) != (self.left_row_count, self.right_row_count):
            raise ValidationError("snapshot diff row counts do not replay")
        expected_changed_fields = sum(len(item.changed_fields) for item in self.items)
        if expected_changed_fields != self.changed_field_count:
            raise ValidationError("snapshot diff changed field count does not replay")
        if (self.summary.diff_id, self.summary.left_snapshot_id, self.summary.right_snapshot_id, self.summary.left_snapshot_address, self.summary.right_snapshot_address, self.summary.left_runtime_id, self.summary.right_runtime_id, self.summary.left_query_address, self.summary.right_query_address, self.summary.left_row_count, self.summary.right_row_count, self.summary.added_count, self.summary.removed_count, self.summary.changed_count, self.summary.unchanged_count, self.summary.left_accepted, self.summary.right_accepted, self.summary.left_state, self.summary.right_state, self.summary.direction, self.summary.state_transition, self.summary.changed_field_count) != (self.diff_id, self.left_snapshot_id, self.right_snapshot_id, self.left_snapshot_address, self.right_snapshot_address, self.left_runtime_id, self.right_runtime_id, self.left_query_address, self.right_query_address, self.left_row_count, self.right_row_count, self.added_count, self.removed_count, self.changed_count, self.unchanged_count, self.left_accepted, self.right_accepted, self.left_state, self.right_state, self.direction, self.state_transition, self.changed_field_count):
            raise ValidationError("snapshot diff summary does not replay")
        if self.manifest.diff_id != self.diff_id or self.manifest.files != FILES or self.manifest.artifact_addresses != (address_items(self.items), self.summary.content_address):
            raise ValidationError("snapshot diff manifest does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("snapshot diff crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("snapshot diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field).to_dict() if hasattr(getattr(self, field), "to_dict") else [item.to_dict() for item in getattr(self, field)] if field == "items" else getattr(self, field) for field in self.FIELDS}

    def summary_document(self) -> dict[str, Any]:
        return self.summary.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot diff")
        _strict(value, set(cls.FIELDS), "snapshot diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff):
        raise ValidationError("snapshot diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _item(ordinal: int, left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem:
    left_row = dict(left or {})
    right_row = dict(right or {})
    source = left_row or right_row
    if not left_row:
        change = "added"
    elif not right_row:
        change = "removed"
    elif _semantic(left_row) == _semantic(right_row):
        change = "unchanged"
    else:
        change = "changed"
    body = {"ordinal": ordinal, "identity": _identity(source), "resource": source["resource"], "stage": source["stage"], "component": source["component"], "name": source["name"], "change": change, "left_row_address": left_row.get("content_address", ""), "right_row_address": right_row.get("content_address", ""), "left_row": left_row, "right_row": right_row, "changed_fields": _changed_fields(left_row, right_row), "content_address": ITEM_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem(**(body | {"content_address": address_item(provisional)}))


def build_diff(left: snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot, right: snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot, *, diff_id: str = DEFAULT_DIFF_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff:
    if not isinstance(left, snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) or not isinstance(right, snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot):
        raise ValidationError("snapshot diff requires typed snapshots")
    left = snapshot_model.verify_snapshot(left)
    right = snapshot_model.verify_snapshot(right)
    if left.query is None or right.query is None:
        raise ValidationError("snapshot diff requires snapshots with attached query rows")
    left_rows = {(_identity(row.to_dict())): row.to_dict() for row in left.query.rows}
    right_rows = {(_identity(row.to_dict())): row.to_dict() for row in right.query.rows}
    if len(left_rows) != len(left.query.rows) or len(right_rows) != len(right.query.rows):
        raise ValidationError("snapshot diff requires unique row identities")
    identities = sorted(set(left_rows) | set(right_rows))
    items = tuple(_item(ordinal, left_rows.get(identity), right_rows.get(identity)) for ordinal, identity in enumerate(identities, 1))
    counts = {change + "_count": sum(item.change == change for item in items) for change in CHANGES}
    changed_field_count = sum(len(item.changed_fields) for item in items)
    direction = _direction(left.accepted, right.accepted, bool(counts["added_count"] or counts["removed_count"] or counts["changed_count"]))
    state_transition = f"{left.state}->{right.state}"
    summary_body = {"diff_id": diff_id, "left_snapshot_id": left.snapshot_id, "right_snapshot_id": right.snapshot_id, "left_snapshot_address": left.content_address, "right_snapshot_address": right.content_address, "left_runtime_id": left.runtime_id, "right_runtime_id": right.runtime_id, "left_query_address": left.query_address, "right_query_address": right.query_address, "left_row_count": len(left.query.rows), "right_row_count": len(right.query.rows), **counts, "left_accepted": left.accepted, "right_accepted": right.accepted, "left_state": left.state, "right_state": right.state, "direction": direction, "state_transition": state_transition, "changed_field_count": changed_field_count, "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary(**summary_body)
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    manifest_body = {"diff_id": diff_id, "files": FILES, "artifact_addresses": (address_items(items), summary.content_address), "content_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest(**manifest_body)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {"diff_id": diff_id, "version": VERSION, "boundary": BOUNDARY, "left_snapshot_id": left.snapshot_id, "right_snapshot_id": right.snapshot_id, "left_snapshot_address": left.content_address, "right_snapshot_address": right.content_address, "left_runtime_id": left.runtime_id, "right_runtime_id": right.runtime_id, "left_query_address": left.query_address, "right_query_address": right.query_address, "left_row_count": len(left.query.rows), "right_row_count": len(right.query.rows), **counts, "left_accepted": left.accepted, "right_accepted": right.accepted, "left_state": left.state, "right_state": right.state, "direction": direction, "state_transition": state_transition, "changed_field_count": changed_field_count, "manifest": manifest, "summary": summary, "items": items, "content_address": DIFF_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff(**(body | {"content_address": address_diff(provisional)}))


def diff_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff.from_mapping(value)


def diff_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> str:
    return canonical_json(diff_from_mapping(value.to_dict()).to_dict())


def items_document(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> dict[str, Any]:
    value = diff_from_mapping(value.to_dict())
    return {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)}


def items_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> str:
    return canonical_json(items_document(value))


def summary_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> str:
    return canonical_json(diff_from_mapping(value.to_dict()).summary.to_dict())


def diff_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> str:
    value = diff_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ITEM_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        writer.writerow({field: json.dumps(row[field], ensure_ascii=False, sort_keys=True) if isinstance(row[field], (dict, list, tuple)) else row[field] for field in ITEM_FIELDS})
    return stream.getvalue()


def render_diff_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> str:
    value = diff_from_mapping(value.to_dict())
    lines = ["# Runtime Query Snapshot Diff", "", f"- Diff: `{value.diff_id}`", f"- Direction: `{value.direction}`", f"- State transition: `{value.state_transition}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Unchanged: `{value.unchanged_count}`", f"- Changed fields: `{value.changed_field_count}`", f"- Address: `{value.content_address}`", "", "| # | identity | change | left row | right row | fields |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.identity}` | `{item.change}` | `{item.left_row_address}` | `{item.right_row_address}` | `{', '.join(item.changed_fields)}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def manifest_document(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> dict[str, Any]:
    return diff_from_mapping(value.to_dict()).manifest.to_dict()


def summary_document(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> dict[str, Any]:
    return diff_from_mapping(value.to_dict()).summary.to_dict()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes(canonical_bytes(value))


def persist_diff(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff):
        raise ValidationError("snapshot diff persistence requires a typed diff")
    value = diff_from_mapping(value.to_dict())
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("snapshot diff destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-runtime-query-snapshot-diff-", dir=str(parent)))
    try:
        documents = {"manifest.json": manifest_document(value), "diff.json": value.to_dict(), "items.json": items_document(value), "summary.json": summary_document(value)}
        for filename in FILES:
            _write(temporary / filename, documents[filename])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("snapshot diff destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("snapshot diff artifact is not valid JSON") from error
    return _mapping(value, "snapshot diff artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_bytes()
    except OSError as error:
        raise ValidationError("snapshot diff artifact cannot be read") from error
    if actual != canonical_bytes(value):
        raise ValidationError("snapshot diff artifact is not canonical")


def load_diff(destination: str | Path):
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("snapshot diff destination must be a directory")
    entries = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in entries)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in entries):
        raise ValidationError("snapshot diff directory does not contain the exact file set")
    raw = {filename: _read_json(destination / filename) for filename in FILES}
    for filename, document in raw.items():
        _read_canonical(destination / filename, document)
    value = diff_from_mapping(raw["diff.json"])
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest.from_mapping(raw["manifest.json"])
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary.from_mapping(raw["summary.json"])
    items = raw["items.json"]
    _strict(items, set(ITEMS_FIELDS), "snapshot diff items")
    tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem.from_mapping(item) for item in _sequence(items["items"], "snapshot diff item artifact", MAX_ITEMS))
    if manifest.to_dict() != value.manifest.to_dict() or summary.to_dict() != value.summary.to_dict() or canonical_bytes(items) != canonical_bytes(items_document(value)):
        raise ValidationError("snapshot diff artifacts do not replay")
    return value


def run_diff(left: snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot, right: snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot, *, diff_id: str = DEFAULT_DIFF_ID, destination: str | Path | None = None, overwrite: bool = False):
    value = build_diff(left, right, diff_id=diff_id)
    if destination is not None:
        persist_diff(value, destination, overwrite=overwrite)
    return value


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff item", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "identity": {"type": "string"}, "resource": {"type": "string"}, "stage": {"type": "string"}, "component": {"type": "string"}, "name": {"type": "string"}, "change": {"enum": list(CHANGES)}, "left_row_address": {"type": "string"}, "right_row_address": {"type": "string"}, "left_row": {"type": "object", "additionalProperties": False, "properties": snapshot_model.query_model.row_schema()["properties"]}, "right_row": {"type": "object", "additionalProperties": False, "properties": snapshot_model.query_model.row_schema()["properties"]}, "changed_fields": {"type": "array", "items": {"enum": list(SEMANTIC_ROW_FIELDS)}}, "content_address": {"type": "string", "pattern": "^" + ITEM_PREFIX + ":"}}}


def items_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff items", "type": "object", "additionalProperties": False, "required": list(ITEMS_FIELDS), "properties": {"items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string", "pattern": "^" + ITEMS_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"diff_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"diff_id": {"type": "string"}, "left_snapshot_id": {"type": "string"}, "right_snapshot_id": {"type": "string"}, "left_snapshot_address": {"type": "string"}, "right_snapshot_address": {"type": "string"}, "left_runtime_id": {"type": "string"}, "right_runtime_id": {"type": "string"}, "left_query_address": {"type": "string"}, "right_query_address": {"type": "string"}, "left_row_count": {"type": "integer", "minimum": 0}, "right_row_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "left_accepted": {"type": "boolean"}, "right_accepted": {"type": "boolean"}, "left_state": {"enum": list(snapshot_model.STATES)}, "right_state": {"enum": list(snapshot_model.STATES)}, "direction": {"enum": list(DIRECTIONS)}, "state_transition": {"type": "string"}, "changed_field_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string", "pattern": "^" + SUMMARY_PREFIX + ":"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "left_snapshot_id": {"type": "string"}, "right_snapshot_id": {"type": "string"}, "left_snapshot_address": {"type": "string"}, "right_snapshot_address": {"type": "string"}, "left_runtime_id": {"type": "string"}, "right_runtime_id": {"type": "string"}, "left_query_address": {"type": "string"}, "right_query_address": {"type": "string"}, "left_row_count": {"type": "integer", "minimum": 0}, "right_row_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "left_accepted": {"type": "boolean"}, "right_accepted": {"type": "boolean"}, "left_state": {"enum": list(snapshot_model.STATES)}, "right_state": {"enum": list(snapshot_model.STATES)}, "direction": {"enum": list(DIRECTIONS)}, "state_transition": {"type": "string"}, "changed_field_count": {"type": "integer", "minimum": 0}, "manifest": {"type": "object"}, "summary": {"type": "object"}, "items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "items_prefix": ITEMS_PREFIX, "files": list(FILES), "changes": list(CHANGES), "directions": list(DIRECTIONS), "max_items": MAX_ITEMS, "semantic_row_fields": list(SEMANTIC_ROW_FIELDS), "features": ["stable runtime-query row identities", "added removed changed and unchanged classification", "changed-field evidence", "receipt-address deltas", "exact four-file persistence", "canonical reload verification", "atomic writes", "JSON CSV and Markdown projections"]}


__all__ = ["BOUNDARY", "CHANGES", "DEFAULT_DIFF_ID", "DIFF_FIELDS", "DIFF_PREFIX", "DIRECTIONS", "FILES", "ITEM_FIELDS", "ITEM_PREFIX", "ITEMS_FIELDS", "ITEMS_PREFIX", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ITEMS", "SEMANTIC_ROW_FIELDS", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffItem", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffSummary", "address_diff", "address_item", "address_items", "address_manifest", "address_summary", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "items_document", "items_json", "items_schema", "load_diff", "manifest_document", "manifest_schema", "persist_diff", "render_diff_markdown", "run_diff", "summary_json", "summary_document", "summary_schema"]
