"""Longitudinal diffs between persisted runtime-query snapshot handoffs.

This boundary compares two value-free query handoffs without reopening their
source archives.  Query definitions must match exactly, and rows are paired by
the stable public identity ``(resource, identity, field)``.  The result keeps
both endpoint receipts, structural field deltas, and enough bounded metadata
for independent replay and review.
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
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot as snapshot_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = snapshot_model.VERSION + "-comparison-v1"
BOUNDARY = snapshot_model.BOUNDARY + "_comparison"
DIFF_PREFIX = snapshot_model.SNAPSHOT_PREFIX + "-comparison-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
ITEMS_PREFIX = DIFF_PREFIX + "-items"
MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
SUMMARY_PREFIX = DIFF_PREFIX + "-summary"
DEFAULT_DIFF_ID = "policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-comparison"
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "mixed", "unchanged")
FILES = ("manifest.json", "diff.json", "items.json", "summary.json")
MANIFEST_ARTIFACT_FILES = ("items.json", "summary.json")
MAX_ITEMS = snapshot_model.query_model.MAX_LIMIT * 2
SHAPE_FIELDS = ("resources", "change_filter", "item_resource_filter", "identity_filter", "component_filter", "field_filter", "direction_filter", "state_transition_filter", "address_filter", "text_filter", "offset", "limit")
SEMANTIC_ROW_FIELDS = tuple(field for field in snapshot_model.query_model.ROW_FIELDS if field not in {"resource", "ordinal", "identity", "field", "content_address"})
ITEM_FIELDS = ("ordinal", "key", "resource", "identity", "field", "change", "left_row_address", "right_row_address", "left_row", "right_row", "changed_fields", "content_address")
ITEMS_FIELDS = ("items", "content_address")
MANIFEST_FIELDS = ("diff_id", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("diff_id", "left_snapshot_id", "right_snapshot_id", "left_snapshot_address", "right_snapshot_address", "left_diff_id", "right_diff_id", "left_diff_address", "right_diff_address", "left_query_address", "right_query_address", "left_query_audit_address", "right_query_audit_address", "left_source_left_snapshot_id", "left_source_right_snapshot_id", "right_source_left_snapshot_id", "right_source_right_snapshot_id", "left_row_count", "right_row_count", "added_count", "removed_count", "changed_count", "unchanged_count", "left_diff_verified", "right_diff_verified", "left_query_audit_accepted", "right_query_audit_accepted", "left_accepted", "right_accepted", "left_state", "right_state", "direction", "state_transition", "left_query_shape", "right_query_shape", "query_shape_match", "changed_field_count", "content_address")
DIFF_FIELDS = ("diff_id", "version", "boundary", "left_snapshot_id", "right_snapshot_id", "left_snapshot_address", "right_snapshot_address", "left_diff_id", "right_diff_id", "left_diff_address", "right_diff_address", "left_query_address", "right_query_address", "left_query_audit_address", "right_query_audit_address", "left_source_left_snapshot_id", "left_source_right_snapshot_id", "right_source_left_snapshot_id", "right_source_right_snapshot_id", "left_row_count", "right_row_count", "added_count", "removed_count", "changed_count", "unchanged_count", "left_diff_verified", "right_diff_verified", "left_query_audit_accepted", "right_query_audit_accepted", "left_accepted", "right_accepted", "left_state", "right_state", "direction", "state_transition", "left_query_shape", "right_query_shape", "query_shape_match", "changed_field_count", "manifest", "summary", "items", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 512, required=required)
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


def _query_shape(value: Any, field: str = "query shape") -> dict[str, Any]:
    value = _mapping(value, field)
    _strict(value, set(SHAPE_FIELDS), field)
    selected = _sequence(value["resources"], f"{field} resources", len(snapshot_model.query_model.RESOURCES))
    if not selected or len(set(selected)) != len(selected) or any(item not in snapshot_model.query_model.RESOURCES for item in selected):
        raise ValidationError(f"{field} resources are invalid")
    resources = tuple(item for item in snapshot_model.query_model.RESOURCES if item in selected)
    change_filter = _label(value["change_filter"], f"{field} change filter")
    if change_filter and change_filter not in snapshot_model.diff_model.CHANGES:
        raise ValidationError(f"{field} change filter is unsupported")
    item_resource_filter = _label(value["item_resource_filter"], f"{field} item resource filter")
    identity_filter = _text(value["identity_filter"], f"{field} identity filter", 1024, required=False)
    component_filter = _label(value["component_filter"], f"{field} component filter")
    field_filter = _label(value["field_filter"], f"{field} field filter")
    if field_filter and field_filter not in snapshot_model.diff_model.SEMANTIC_ROW_FIELDS:
        raise ValidationError(f"{field} field filter is unsupported")
    direction_filter = _label(value["direction_filter"], f"{field} direction filter")
    if direction_filter and direction_filter not in snapshot_model.diff_model.DIRECTIONS:
        raise ValidationError(f"{field} direction filter is unsupported")
    state_transition_filter = _label(value["state_transition_filter"], f"{field} state transition filter")
    address_filter = _address(value["address_filter"], f"{field} address filter")
    text_filter = _text(value["text_filter"], f"{field} text filter", 1024, required=False)
    offset = _count(value["offset"], f"{field} offset", snapshot_model.query_model.MAX_TOTAL_COUNT)
    limit = _count(value["limit"], f"{field} limit", snapshot_model.query_model.MAX_LIMIT, positive=True)
    return {"resources": resources, "change_filter": change_filter, "item_resource_filter": item_resource_filter, "identity_filter": identity_filter, "component_filter": component_filter, "field_filter": field_filter, "direction_filter": direction_filter, "state_transition_filter": state_transition_filter, "address_filter": address_filter, "text_filter": text_filter, "offset": offset, "limit": limit}


def _shape_from_query(value: Any) -> dict[str, Any]:
    return _query_shape({field: getattr(value, field) for field in SHAPE_FIELDS})


def _query_row(value: Any, field: str) -> dict[str, Any]:
    value = _mapping(value, field)
    if not value:
        return {}
    _strict(value, set(snapshot_model.query_model.ROW_FIELDS), field)
    return dict(value)


def _row_key(row: Mapping[str, Any]) -> str:
    return "|".join(str(row[field]) for field in ("resource", "identity", "field"))


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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem:
    """One stable query-row comparison between two persisted handoffs."""

    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, key: str, resource: str, identity: str, field: str, change: str, left_row_address: str, right_row_address: str, left_row: Mapping[str, Any], right_row: Mapping[str, Any], changed_fields: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "comparison item ordinal", MAX_ITEMS, positive=True)
        self.key = _text(key, "comparison item key", 2048, required=True)
        self.resource = _label(resource, "comparison item resource", required=True)
        if self.resource not in snapshot_model.query_model.RESOURCES:
            raise ValidationError("comparison item resource is unsupported")
        self.identity = _text(identity, "comparison item identity", 1024, required=False)
        self.field = _label(field, "comparison item field")
        if self.field and self.field not in snapshot_model.diff_model.SEMANTIC_ROW_FIELDS:
            raise ValidationError("comparison item field is unsupported")
        self.change = _label(change, "comparison item change", required=True)
        if self.change not in CHANGES:
            raise ValidationError("comparison item change is unsupported")
        self.left_row_address = _address(left_row_address, "comparison left row address", snapshot_model.query_model.ROW_PREFIX)
        self.right_row_address = _address(right_row_address, "comparison right row address", snapshot_model.query_model.ROW_PREFIX)
        self.left_row = _query_row(left_row, "comparison left row")
        self.right_row = _query_row(right_row, "comparison right row")
        self.changed_fields = tuple(_label(item, "comparison changed field", required=True) for item in _sequence(changed_fields, "comparison changed fields", len(SEMANTIC_ROW_FIELDS)))
        if len(set(self.changed_fields)) != len(self.changed_fields) or any(item not in SEMANTIC_ROW_FIELDS for item in self.changed_fields):
            raise ValidationError("comparison changed fields are invalid")
        self.content_address = _address(content_address, "comparison item address", ITEM_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        source = self.left_row or self.right_row
        if not source or self.key != _row_key(source) or self.resource != source["resource"] or self.identity != source["identity"] or self.field != source["field"]:
            raise ValidationError("comparison item stable identity does not replay")
        if self.left_row and self.left_row_address != self.left_row["content_address"] or not self.left_row and self.left_row_address:
            raise ValidationError("comparison left row address does not replay")
        if self.right_row and self.right_row_address != self.right_row["content_address"] or not self.right_row and self.right_row_address:
            raise ValidationError("comparison right row address does not replay")
        if self.change == "added" and (self.left_row or not self.right_row):
            raise ValidationError("added comparison item does not have one right row")
        if self.change == "removed" and (not self.left_row or self.right_row):
            raise ValidationError("removed comparison item does not have one left row")
        if self.change in {"changed", "unchanged"} and (not self.left_row or not self.right_row):
            raise ValidationError("paired comparison item does not have two rows")
        if self.change == "unchanged" and _semantic(self.left_row) != _semantic(self.right_row):
            raise ValidationError("unchanged comparison item contains a semantic difference")
        if self.change == "changed" and _semantic(self.left_row) == _semantic(self.right_row):
            raise ValidationError("changed comparison item contains no semantic difference")
        if self.changed_fields != _changed_fields(self.left_row, self.right_row):
            raise ValidationError("comparison changed fields do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("comparison item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("comparison item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison item")
        _strict(value, set(cls.FIELDS), "comparison item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem):
        raise ValidationError("comparison item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


def address_items(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem) for item in typed):
        raise ValidationError("comparison items address requires typed items")
    return content_hash({"items": [item.to_dict() for item in typed]}, prefix=ITEMS_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, diff_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.diff_id = _label(diff_id, "comparison manifest diff ID", required=True)
        self.files = tuple(_label(item, "comparison manifest file", required=True) for item in _sequence(files, "comparison manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "comparison manifest artifact address", required=True) for item in _sequence(artifact_addresses, "comparison manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "comparison manifest address", MANIFEST_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("comparison manifest does not close the public file boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("comparison manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison manifest")
        _strict(value, set(cls.FIELDS), "comparison manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest):
        raise ValidationError("comparison manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, diff_id: str, left_snapshot_id: str, right_snapshot_id: str, left_snapshot_address: str, right_snapshot_address: str, left_diff_id: str, right_diff_id: str, left_diff_address: str, right_diff_address: str, left_query_address: str, right_query_address: str, left_query_audit_address: str, right_query_audit_address: str, left_source_left_snapshot_id: str, left_source_right_snapshot_id: str, right_source_left_snapshot_id: str, right_source_right_snapshot_id: str, left_row_count: int, right_row_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, left_diff_verified: bool, right_diff_verified: bool, left_query_audit_accepted: bool, right_query_audit_accepted: bool, left_accepted: bool, right_accepted: bool, left_state: str, right_state: str, direction: str, state_transition: str, left_query_shape: Mapping[str, Any], right_query_shape: Mapping[str, Any], query_shape_match: bool, changed_field_count: int, content_address: str) -> None:
        self.diff_id = _label(diff_id, "comparison summary diff ID", required=True)
        self.left_snapshot_id = _label(left_snapshot_id, "comparison summary left snapshot ID", required=True)
        self.right_snapshot_id = _label(right_snapshot_id, "comparison summary right snapshot ID", required=True)
        self.left_snapshot_address = _address(left_snapshot_address, "comparison summary left snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=True)
        self.right_snapshot_address = _address(right_snapshot_address, "comparison summary right snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=True)
        self.left_diff_id = _label(left_diff_id, "comparison summary left diff ID", required=True)
        self.right_diff_id = _label(right_diff_id, "comparison summary right diff ID", required=True)
        self.left_diff_address = _address(left_diff_address, "comparison summary left diff address", snapshot_model.diff_model.DIFF_PREFIX, required=True)
        self.right_diff_address = _address(right_diff_address, "comparison summary right diff address", snapshot_model.diff_model.DIFF_PREFIX, required=True)
        self.left_query_address = _address(left_query_address, "comparison summary left query address", snapshot_model.query_model.QUERY_PREFIX, required=True)
        self.right_query_address = _address(right_query_address, "comparison summary right query address", snapshot_model.query_model.QUERY_PREFIX, required=True)
        self.left_query_audit_address = _address(left_query_audit_address, "comparison summary left query audit address", snapshot_model.query_audit_model.AUDIT_PREFIX, required=True)
        self.right_query_audit_address = _address(right_query_audit_address, "comparison summary right query audit address", snapshot_model.query_audit_model.AUDIT_PREFIX, required=True)
        self.left_source_left_snapshot_id = _label(left_source_left_snapshot_id, "comparison summary left source left snapshot ID", required=True)
        self.left_source_right_snapshot_id = _label(left_source_right_snapshot_id, "comparison summary left source right snapshot ID", required=True)
        self.right_source_left_snapshot_id = _label(right_source_left_snapshot_id, "comparison summary right source left snapshot ID", required=True)
        self.right_source_right_snapshot_id = _label(right_source_right_snapshot_id, "comparison summary right source right snapshot ID", required=True)
        self.left_row_count = _count(left_row_count, "comparison summary left row count", MAX_ITEMS)
        self.right_row_count = _count(right_row_count, "comparison summary right row count", MAX_ITEMS)
        self.added_count = _count(added_count, "comparison summary added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "comparison summary removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "comparison summary changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "comparison summary unchanged count", MAX_ITEMS)
        self.left_diff_verified = _bool(left_diff_verified, "comparison summary left diff verification")
        self.right_diff_verified = _bool(right_diff_verified, "comparison summary right diff verification")
        self.left_query_audit_accepted = _bool(left_query_audit_accepted, "comparison summary left query audit acceptance")
        self.right_query_audit_accepted = _bool(right_query_audit_accepted, "comparison summary right query audit acceptance")
        self.left_accepted = _bool(left_accepted, "comparison summary left acceptance")
        self.right_accepted = _bool(right_accepted, "comparison summary right acceptance")
        self.left_state = _label(left_state, "comparison summary left state", required=True)
        self.right_state = _label(right_state, "comparison summary right state", required=True)
        if self.left_state not in snapshot_model.STATES or self.right_state not in snapshot_model.STATES:
            raise ValidationError("comparison summary state is unsupported")
        self.direction = _label(direction, "comparison summary direction", required=True)
        if self.direction not in DIRECTIONS:
            raise ValidationError("comparison summary direction is unsupported")
        self.state_transition = _label(state_transition, "comparison summary state transition", required=True)
        self.left_query_shape = _query_shape(left_query_shape, "comparison left query shape")
        self.right_query_shape = _query_shape(right_query_shape, "comparison right query shape")
        self.query_shape_match = _bool(query_shape_match, "comparison query shape match")
        self.changed_field_count = _count(changed_field_count, "comparison summary changed field count", MAX_ITEMS * len(SEMANTIC_ROW_FIELDS))
        self.content_address = _address(content_address, "comparison summary address", SUMMARY_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.added_count + self.removed_count + self.changed_count + self.unchanged_count > MAX_ITEMS or not self.query_shape_match or self.left_query_shape != self.right_query_shape:
            raise ValidationError("comparison summary counts or query shape do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("comparison summary crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("comparison summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison summary")
        _strict(value, set(cls.FIELDS), "comparison summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary):
        raise ValidationError("comparison summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff:
    """A durable longitudinal comparison of two verified query handoffs."""

    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, version: str, boundary: str, left_snapshot_id: str, right_snapshot_id: str, left_snapshot_address: str, right_snapshot_address: str, left_diff_id: str, right_diff_id: str, left_diff_address: str, right_diff_address: str, left_query_address: str, right_query_address: str, left_query_audit_address: str, right_query_audit_address: str, left_source_left_snapshot_id: str, left_source_right_snapshot_id: str, right_source_left_snapshot_id: str, right_source_right_snapshot_id: str, left_row_count: int, right_row_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, left_diff_verified: bool, right_diff_verified: bool, left_query_audit_accepted: bool, right_query_audit_accepted: bool, left_accepted: bool, right_accepted: bool, left_state: str, right_state: str, direction: str, state_transition: str, left_query_shape: Mapping[str, Any], right_query_shape: Mapping[str, Any], query_shape_match: bool, changed_field_count: int, manifest: Mapping[str, Any] | DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest, summary: Mapping[str, Any] | DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary, items: Sequence[Mapping[str, Any] | DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem], content_address: str) -> None:
        self.diff_id = _label(diff_id, "comparison diff ID", required=True)
        self.version = _text(version, "comparison diff version", 512, required=True)
        self.boundary = _text(boundary, "comparison diff boundary", 512, required=True)
        self.left_snapshot_id = _label(left_snapshot_id, "comparison left snapshot ID", required=True)
        self.right_snapshot_id = _label(right_snapshot_id, "comparison right snapshot ID", required=True)
        self.left_snapshot_address = _address(left_snapshot_address, "comparison left snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=True)
        self.right_snapshot_address = _address(right_snapshot_address, "comparison right snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=True)
        self.left_diff_id = _label(left_diff_id, "comparison left diff ID", required=True)
        self.right_diff_id = _label(right_diff_id, "comparison right diff ID", required=True)
        self.left_diff_address = _address(left_diff_address, "comparison left diff address", snapshot_model.diff_model.DIFF_PREFIX, required=True)
        self.right_diff_address = _address(right_diff_address, "comparison right diff address", snapshot_model.diff_model.DIFF_PREFIX, required=True)
        self.left_query_address = _address(left_query_address, "comparison left query address", snapshot_model.query_model.QUERY_PREFIX, required=True)
        self.right_query_address = _address(right_query_address, "comparison right query address", snapshot_model.query_model.QUERY_PREFIX, required=True)
        self.left_query_audit_address = _address(left_query_audit_address, "comparison left query audit address", snapshot_model.query_audit_model.AUDIT_PREFIX, required=True)
        self.right_query_audit_address = _address(right_query_audit_address, "comparison right query audit address", snapshot_model.query_audit_model.AUDIT_PREFIX, required=True)
        self.left_source_left_snapshot_id = _label(left_source_left_snapshot_id, "comparison left source left snapshot ID", required=True)
        self.left_source_right_snapshot_id = _label(left_source_right_snapshot_id, "comparison left source right snapshot ID", required=True)
        self.right_source_left_snapshot_id = _label(right_source_left_snapshot_id, "comparison right source left snapshot ID", required=True)
        self.right_source_right_snapshot_id = _label(right_source_right_snapshot_id, "comparison right source right snapshot ID", required=True)
        self.left_row_count = _count(left_row_count, "comparison left row count", MAX_ITEMS)
        self.right_row_count = _count(right_row_count, "comparison right row count", MAX_ITEMS)
        self.added_count = _count(added_count, "comparison added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "comparison removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "comparison changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "comparison unchanged count", MAX_ITEMS)
        self.left_diff_verified = _bool(left_diff_verified, "comparison left diff verification")
        self.right_diff_verified = _bool(right_diff_verified, "comparison right diff verification")
        self.left_query_audit_accepted = _bool(left_query_audit_accepted, "comparison left query audit acceptance")
        self.right_query_audit_accepted = _bool(right_query_audit_accepted, "comparison right query audit acceptance")
        self.left_accepted = _bool(left_accepted, "comparison left acceptance")
        self.right_accepted = _bool(right_accepted, "comparison right acceptance")
        self.left_state = _label(left_state, "comparison left state", required=True)
        self.right_state = _label(right_state, "comparison right state", required=True)
        if self.left_state not in snapshot_model.STATES or self.right_state not in snapshot_model.STATES:
            raise ValidationError("comparison state is unsupported")
        self.direction = _label(direction, "comparison direction", required=True)
        if self.direction not in DIRECTIONS:
            raise ValidationError("comparison direction is unsupported")
        self.state_transition = _label(state_transition, "comparison state transition", required=True)
        self.left_query_shape = _query_shape(left_query_shape, "comparison left query shape")
        self.right_query_shape = _query_shape(right_query_shape, "comparison right query shape")
        self.query_shape_match = _bool(query_shape_match, "comparison query shape match")
        self.changed_field_count = _count(changed_field_count, "comparison changed field count", MAX_ITEMS * len(SEMANTIC_ROW_FIELDS))
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary.from_mapping(summary)
        self.items = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem.from_mapping(item) for item in _sequence(items, "comparison items", MAX_ITEMS))
        self.content_address = _address(content_address, "comparison diff address", DIFF_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("comparison version or boundary is not current")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or len({item.key for item in self.items}) != len(self.items):
            raise ValidationError("comparison item order or identity is not conserved")
        counts = tuple(sum(item.change == change for item in self.items) for change in CHANGES)
        if counts != (self.added_count, self.removed_count, self.changed_count, self.unchanged_count):
            raise ValidationError("comparison item counts do not replay")
        if (sum(bool(item.left_row) for item in self.items), sum(bool(item.right_row) for item in self.items)) != (self.left_row_count, self.right_row_count):
            raise ValidationError("comparison row counts do not replay")
        if sum(len(item.changed_fields) for item in self.items) != self.changed_field_count:
            raise ValidationError("comparison changed field count does not replay")
        if not self.query_shape_match or self.left_query_shape != self.right_query_shape:
            raise ValidationError("comparison query shape does not replay")
        summary_values = tuple(self.summary.to_dict()[field] for field in SUMMARY_FIELDS if field != "content_address")
        expected_values = tuple(self.to_dict()[field] for field in SUMMARY_FIELDS if field != "content_address")
        if summary_values != expected_values:
            raise ValidationError("comparison summary does not replay")
        if self.manifest.diff_id != self.diff_id or self.manifest.files != FILES or self.manifest.artifact_addresses != (address_items(self.items), self.summary.content_address):
            raise ValidationError("comparison manifest does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("comparison diff crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("comparison diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field).to_dict() if hasattr(getattr(self, field), "to_dict") else [item.to_dict() for item in getattr(self, field)] if field == "items" else getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison diff")
        _strict(value, set(cls.FIELDS), "comparison diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff):
        raise ValidationError("comparison diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _item(ordinal: int, left: Mapping[str, Any] | None, right: Mapping[str, Any] | None):
    left_row = dict(left or {})
    right_row = dict(right or {})
    source = left_row or right_row
    if not source:
        raise ValidationError("comparison item requires at least one query row")
    if not left_row:
        change = "added"
    elif not right_row:
        change = "removed"
    elif _semantic(left_row) == _semantic(right_row):
        change = "unchanged"
    else:
        change = "changed"
    body = {"ordinal": ordinal, "key": _row_key(source), "resource": source["resource"], "identity": source["identity"], "field": source["field"], "change": change, "left_row_address": left_row.get("content_address", ""), "right_row_address": right_row.get("content_address", ""), "left_row": left_row, "right_row": right_row, "changed_fields": _changed_fields(left_row, right_row), "content_address": ITEM_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem(**(body | {"content_address": address_item(provisional)}))


def _source_rows(value: Any) -> dict[str, dict[str, Any]]:
    rows = {(_row_key(row.to_dict())): row.to_dict() for row in value.query.rows}
    if len(rows) != len(value.query.rows):
        raise ValidationError("comparison requires unique query-row identities")
    return rows


def build_diff(left: snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot, right: snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot, *, diff_id: str = DEFAULT_DIFF_ID):
    if not isinstance(left, snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot) or not isinstance(right, snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot):
        raise ValidationError("comparison requires typed query snapshots")
    left = snapshot_model.verify_snapshot(left)
    right = snapshot_model.verify_snapshot(right)
    if left.query is None or right.query is None or left.query_audit is None or right.query_audit is None:
        raise ValidationError("comparison requires query and audit attachments")
    left_shape = _shape_from_query(left.query)
    right_shape = _shape_from_query(right.query)
    if left_shape != right_shape:
        raise ValidationError("comparison requires identical query shapes")
    left_rows = _source_rows(left)
    right_rows = _source_rows(right)
    keys = sorted(set(left_rows) | set(right_rows))
    items = tuple(_item(ordinal, left_rows.get(key), right_rows.get(key)) for ordinal, key in enumerate(keys, 1))
    counts = {change + "_count": sum(item.change == change for item in items) for change in CHANGES}
    changed_field_count = sum(len(item.changed_fields) for item in items)
    direction = _direction(left.accepted, right.accepted, bool(counts["added_count"] or counts["removed_count"] or counts["changed_count"]))
    state_transition = f"{left.state}->{right.state}"
    common = {"diff_id": diff_id, "left_snapshot_id": left.snapshot_id, "right_snapshot_id": right.snapshot_id, "left_snapshot_address": left.content_address, "right_snapshot_address": right.content_address, "left_diff_id": left.diff_id, "right_diff_id": right.diff_id, "left_diff_address": left.diff_address, "right_diff_address": right.diff_address, "left_query_address": left.query_address, "right_query_address": right.query_address, "left_query_audit_address": left.query_audit_address, "right_query_audit_address": right.query_audit_address, "left_source_left_snapshot_id": left.left_snapshot_id, "left_source_right_snapshot_id": left.right_snapshot_id, "right_source_left_snapshot_id": right.left_snapshot_id, "right_source_right_snapshot_id": right.right_snapshot_id, "left_row_count": len(left.query.rows), "right_row_count": len(right.query.rows), **counts, "left_diff_verified": left.diff_verified, "right_diff_verified": right.diff_verified, "left_query_audit_accepted": left.query_audit_accepted, "right_query_audit_accepted": right.query_audit_accepted, "left_accepted": left.accepted, "right_accepted": right.accepted, "left_state": left.state, "right_state": right.state, "direction": direction, "state_transition": state_transition, "left_query_shape": left_shape, "right_query_shape": right_shape, "query_shape_match": True, "changed_field_count": changed_field_count}
    summary_body = common | {"content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary(**summary_body)
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    manifest_body = {"diff_id": diff_id, "files": FILES, "artifact_addresses": (address_items(items), summary.content_address), "content_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest(**manifest_body)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = common | {"version": VERSION, "boundary": BOUNDARY, "manifest": manifest, "summary": summary, "items": items, "content_address": DIFF_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff(**(body | {"content_address": address_diff(provisional)}))


def verify_diff(value):
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff):
        raise ValidationError("comparison verification requires a typed diff")
    value._validate()
    if not value.content_address.endswith(":pending") and address_diff(value) != value.content_address:
        raise ValidationError("comparison address verification failed")
    return value


def diff_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff.from_mapping(value)


def diff_json(value) -> str:
    return canonical_json(diff_from_mapping(verify_diff(value).to_dict()).to_dict())


def items_document(value) -> dict[str, Any]:
    value = diff_from_mapping(verify_diff(value).to_dict())
    return {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)}


def items_json(value) -> str:
    return canonical_json(items_document(value))


def summary_document(value) -> dict[str, Any]:
    return diff_from_mapping(verify_diff(value).to_dict()).summary.to_dict()


def summary_json(value) -> str:
    return canonical_json(summary_document(value))


def manifest_document(value) -> dict[str, Any]:
    return diff_from_mapping(verify_diff(value).to_dict()).manifest.to_dict()


def diff_csv(value) -> str:
    value = diff_from_mapping(verify_diff(value).to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ITEM_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        writer.writerow({field: json.dumps(row[field], ensure_ascii=False, sort_keys=True) if isinstance(row[field], (dict, list, tuple)) else row[field] for field in ITEM_FIELDS})
    return stream.getvalue()


def render_diff_markdown(value) -> str:
    value = diff_from_mapping(verify_diff(value).to_dict())
    mark = chr(96)
    lines = ["# Runtime Query Snapshot Handoff Comparison", "", f"- Comparison: {mark}{value.diff_id}{mark}", f"- Direction: {mark}{value.direction}{mark}", f"- State transition: {mark}{value.state_transition}{mark}", f"- Added: {mark}{value.added_count}{mark}", f"- Removed: {mark}{value.removed_count}{mark}", f"- Changed: {mark}{value.changed_count}{mark}", f"- Unchanged: {mark}{value.unchanged_count}{mark}", f"- Changed fields: {mark}{value.changed_field_count}{mark}", f"- Query shape match: {mark}{value.query_shape_match}{mark}", f"- Address: {mark}{value.content_address}{mark}", "", "| # | key | change | left row | right row | fields |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {mark}{item.key}{mark} | {mark}{item.change}{mark} | {mark}{item.left_row_address}{mark} | {mark}{item.right_row_address}{mark} | {', '.join(item.changed_fields)} |" for item in value.items)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes(canonical_bytes(value))


def persist_diff(value, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_diff(value)
    target = Path(destination)
    if target.exists() and (target.is_symlink() or not target.is_dir() or not overwrite):
        raise ValidationError("comparison destination exists; explicit overwrite is required")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
    try:
        documents = {"manifest.json": manifest_document(value), "diff.json": value.to_dict(), "items.json": items_document(value), "summary.json": summary_document(value)}
        for filename in FILES:
            _write(temporary / filename, documents[filename])
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("comparison could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = _mapping(json.loads(raw.decode("utf-8")), f"comparison member {path.name}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"comparison member {path.name} is not valid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"comparison member {path.name} is not canonical")
    return value, raw


def load_diff(destination: str | Path):
    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("comparison source must be a regular directory")
    entries = tuple(root.iterdir())
    if tuple(sorted(item.name for item in entries)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in entries):
        raise ValidationError("comparison directory has an unexpected file set")
    raw = {}
    member_bytes = {}
    for filename in FILES:
        raw[filename], member_bytes[filename] = _read_json(root / filename)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest.from_mapping(raw["manifest.json"])
    value = diff_from_mapping(raw["diff.json"])
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary.from_mapping(raw["summary.json"])
    items = raw["items.json"]
    _strict(items, set(ITEMS_FIELDS), "comparison items")
    tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem.from_mapping(item) for item in _sequence(items["items"], "comparison item artifact", MAX_ITEMS))
    if manifest.to_dict() != value.manifest.to_dict() or summary.to_dict() != value.summary.to_dict() or canonical_bytes(items) != canonical_bytes(items_document(value)):
        raise ValidationError("comparison artifacts do not replay")
    return verify_diff(value)


def run_diff(left: snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot | str | Path, right: snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot | str | Path, *, diff_id: str = DEFAULT_DIFF_ID, destination: str | Path | None = None, overwrite: bool = False):
    if isinstance(left, (str, Path)):
        left = snapshot_model.load_snapshot(left)
    if isinstance(right, (str, Path)):
        right = snapshot_model.load_snapshot(right)
    value = build_diff(left, right, diff_id=diff_id)
    if destination is not None:
        persist_diff(value, destination, overwrite=overwrite)
    return value


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot handoff comparison item", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "key": {"type": "string"}, "resource": {"type": "string", "enum": list(snapshot_model.query_model.RESOURCES)}, "identity": {"type": "string"}, "field": {"type": "string"}, "change": {"enum": list(CHANGES)}, "left_row_address": {"type": "string"}, "right_row_address": {"type": "string"}, "left_row": {"type": "object", "additionalProperties": False, "properties": snapshot_model.query_model.row_schema()["properties"]}, "right_row": {"type": "object", "additionalProperties": False, "properties": snapshot_model.query_model.row_schema()["properties"]}, "changed_fields": {"type": "array", "items": {"enum": list(SEMANTIC_ROW_FIELDS)}}, "content_address": {"type": "string", "pattern": "^" + ITEM_PREFIX + ":"}}}


def items_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot handoff comparison items", "type": "object", "additionalProperties": False, "required": list(ITEMS_FIELDS), "properties": {"items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string", "pattern": "^" + ITEMS_PREFIX + ":"}}}


def _shape_schema() -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": list(SHAPE_FIELDS), "properties": {"resources": {"type": "array", "items": {"enum": list(snapshot_model.query_model.RESOURCES)}}, "change_filter": {"type": "string"}, "item_resource_filter": {"type": "string"}, "identity_filter": {"type": "string"}, "component_filter": {"type": "string"}, "field_filter": {"type": "string"}, "direction_filter": {"type": "string"}, "state_transition_filter": {"type": "string"}, "address_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot handoff comparison manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"diff_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def summary_schema() -> dict[str, Any]:
    properties = {field: {"type": "string"} for field in SUMMARY_FIELDS}
    for field in ("left_snapshot_address", "right_snapshot_address"):
        properties[field] = {"type": "string", "pattern": "^" + snapshot_model.SNAPSHOT_PREFIX + ":"}
    for field in ("left_diff_address", "right_diff_address"):
        properties[field] = {"type": "string", "pattern": "^" + snapshot_model.diff_model.DIFF_PREFIX + ":"}
    for field in ("left_query_address", "right_query_address"):
        properties[field] = {"type": "string", "pattern": "^" + snapshot_model.query_model.QUERY_PREFIX + ":"}
    for field in ("left_query_audit_address", "right_query_audit_address"):
        properties[field] = {"type": "string", "pattern": "^" + snapshot_model.query_audit_model.AUDIT_PREFIX + ":"}
    for field in ("left_row_count", "right_row_count", "added_count", "removed_count", "changed_count", "unchanged_count", "changed_field_count"):
        properties[field] = {"type": "integer", "minimum": 0}
    for field in ("left_diff_verified", "right_diff_verified", "left_query_audit_accepted", "right_query_audit_accepted", "left_accepted", "right_accepted", "query_shape_match"):
        properties[field] = {"type": "boolean"}
    properties["direction"] = {"enum": list(DIRECTIONS)}
    properties["left_state"] = {"enum": list(snapshot_model.STATES)}
    properties["right_state"] = {"enum": list(snapshot_model.STATES)}
    properties["left_query_shape"] = _shape_schema()
    properties["right_query_shape"] = _shape_schema()
    properties["content_address"] = {"type": "string", "pattern": "^" + SUMMARY_PREFIX + ":"}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot handoff comparison summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": properties}


def diff_schema() -> dict[str, Any]:
    properties = {field: {"type": "string"} for field in DIFF_FIELDS}
    properties.update({"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "manifest": {"type": "object"}, "summary": {"type": "object"}, "items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}})
    properties["content_address"] = {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot handoff comparison", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "items_prefix": ITEMS_PREFIX, "files": list(FILES), "changes": list(CHANGES), "directions": list(DIRECTIONS), "shape_fields": list(SHAPE_FIELDS), "semantic_row_fields": list(SEMANTIC_ROW_FIELDS), "max_items": MAX_ITEMS, "features": ["longitudinal persisted handoff comparisons", "exact query-shape matching", "stable resource identity and field pairing", "added removed changed and unchanged classification", "source query and audit receipt retention", "changed-field evidence", "exact four-file persistence", "canonical reload verification", "atomic writes", "JSON CSV and Markdown projections"]}


__all__ = ["BOUNDARY", "CHANGES", "DEFAULT_DIFF_ID", "DIFF_FIELDS", "DIFF_PREFIX", "DIRECTIONS", "FILES", "ITEM_FIELDS", "ITEM_PREFIX", "ITEMS_FIELDS", "ITEMS_PREFIX", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ITEMS", "SEMANTIC_ROW_FIELDS", "SHAPE_FIELDS", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffItem", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffSummary", "address_diff", "address_item", "address_items", "address_manifest", "address_summary", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "items_document", "items_json", "items_schema", "load_diff", "manifest_document", "manifest_schema", "persist_diff", "render_diff_markdown", "run_diff", "summary_document", "summary_json", "summary_schema", "verify_diff"]
