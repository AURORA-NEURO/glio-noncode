"""Deterministic evolution diffs for observability-bundle catalogs.

The catalog is an inventory of independently verified handoffs.  This module
compares two such inventories without reopening source history or exposing
the directories from which either inventory was built.  Labels are stable
identities; ordinals are deliberately excluded from semantic comparison so a
new lexically earlier label cannot manufacture a false content change.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog as catalog_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = catalog_model.VERSION + "-diff-v1"
BOUNDARY = catalog_model.BOUNDARY + "_diff"
DIFF_PREFIX = catalog_model.CATALOG_PREFIX + "-diff"
ENTRY_DIFF_PREFIX = DIFF_PREFIX + "-entry"
DEFAULT_DIFF_ID = "glio-noncode-observability-bundle-catalog-diff"
MAX_ITEMS = catalog_model.MAX_ENTRIES * 2
MAX_ARTIFACTS = MAX_ITEMS * len(catalog_model.bundle_model.ARTIFACT_FILES)
MAX_TEXT = 1024
STATUSES = ("added", "removed", "changed", "unchanged")
STATES = ("unchanged", "added", "removed", "changed", "mixed")

# Ordinal and entry content address are intentionally absent.  Ordinals are
# presentation positions and entry addresses include those positions.
COMPARABLE_FIELDS = (
    "label",
    "bundle_address",
    "manifest_address",
    "pipeline_address",
    "pipeline_state",
    "pipeline_accepted",
    "observability_address",
    "observability_state",
    "audit_address",
    "audit_state",
    "audit_accepted",
    "query_addresses",
    "artifact_count",
)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _label(value: Any, field: str = "observability bundle catalog diff label") -> str:
    return catalog_model._label(value, field)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _delta(value: Any, field: str, maximum: int = MAX_ITEMS) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < -maximum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return catalog_model._public(value)


def _accepted(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry | None) -> int:
    return int(entry is not None and entry.pipeline_accepted and entry.audit_accepted)


def _ready(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry | None) -> int:
    return int(entry is not None and entry.pipeline_accepted and entry.audit_accepted and entry.pipeline_state == "ready" and entry.observability_state == "ready" and entry.audit_state == "complete")


def _projection(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) -> dict[str, Any]:
    return {field: getattr(entry, field) for field in COMPARABLE_FIELDS}


def _entry_delta(left: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry | None, right: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry | None, field: str) -> int:
    left_value = 0 if left is None else int(getattr(left, field))
    right_value = 0 if right is None else int(getattr(right, field))
    return right_value - left_value


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff:
    """One label's comparison across two catalog snapshots."""

    FIELDS = (
        "label",
        "status",
        "left_entry",
        "right_entry",
        "changed_fields",
        "accepted_delta",
        "ready_delta",
        "artifact_count_delta",
        "content_address",
    )

    def __init__(self, label: str, status: str, left_entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry | None, right_entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry | None, changed_fields: Sequence[str], accepted_delta: int, ready_delta: int, artifact_count_delta: int, content_address: str) -> None:
        self.label = _label(label)
        self.status = _text(status, "observability bundle catalog entry diff status", 32)
        if left_entry is not None and not isinstance(left_entry, catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry):
            raise ValidationError("observability bundle catalog entry diff left entry must be typed")
        if right_entry is not None and not isinstance(right_entry, catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry):
            raise ValidationError("observability bundle catalog entry diff right entry must be typed")
        self.left_entry = left_entry
        self.right_entry = right_entry
        self.changed_fields = tuple(_text(field, "observability bundle catalog entry diff changed field", 64) for field in changed_fields)
        self.accepted_delta = _delta(accepted_delta, "observability bundle catalog entry diff accepted delta", 1)
        self.ready_delta = _delta(ready_delta, "observability bundle catalog entry diff ready delta", 1)
        self.artifact_count_delta = _delta(artifact_count_delta, "observability bundle catalog entry diff artifact count delta", len(catalog_model.bundle_model.ARTIFACT_FILES))
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.status not in STATUSES:
            raise ValidationError("observability bundle catalog entry diff status is unsupported")
        if self.left_entry is None and self.right_entry is None:
            raise ValidationError("observability bundle catalog entry diff requires one entry")
        if self.status == "added" and self.left_entry is not None:
            raise ValidationError("added entry diff cannot contain a left entry")
        if self.status == "removed" and self.right_entry is not None:
            raise ValidationError("removed entry diff cannot contain a right entry")
        if self.status in ("changed", "unchanged") and (self.left_entry is None or self.right_entry is None):
            raise ValidationError("paired entry diff status requires both entries")
        if tuple(self.changed_fields) != tuple(sorted(set(self.changed_fields))) or any(field not in COMPARABLE_FIELDS for field in self.changed_fields):
            raise ValidationError("observability bundle catalog entry diff fields are not canonical")
        if self.status == "unchanged" and self.changed_fields:
            raise ValidationError("unchanged entry diff cannot contain changed fields")
        if self.status == "changed" and not self.changed_fields:
            raise ValidationError("changed entry diff must contain changed fields")
        if self.left_entry is not None and self.right_entry is not None:
            expected_fields = tuple(sorted(field for field in COMPARABLE_FIELDS if _projection(self.left_entry)[field] != _projection(self.right_entry)[field]))
            expected_status = "changed" if expected_fields else "unchanged"
            if self.status != expected_status or tuple(self.changed_fields) != expected_fields:
                raise ValidationError("observability bundle catalog entry diff does not conserve field changes")
        if self.accepted_delta != _accepted(self.right_entry) - _accepted(self.left_entry) or self.ready_delta != _ready(self.right_entry) - _ready(self.left_entry) or self.artifact_count_delta != _entry_delta(self.left_entry, self.right_entry, "artifact_count"):
            raise ValidationError("observability bundle catalog entry diff deltas are not derived")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog entry diff content address")
        else:
            _address(self.content_address, "observability bundle catalog entry diff content address", ENTRY_DIFF_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_entry_diff(self) != self.content_address):
            raise ValidationError("observability bundle catalog entry diff address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "status": self.status, "left_entry": None if self.left_entry is None else self.left_entry.to_dict(), "right_entry": None if self.right_entry is None else self.right_entry.to_dict(), "changed_fields": self.changed_fields, "accepted_delta": self.accepted_delta, "ready_delta": self.ready_delta, "artifact_count_delta": self.artifact_count_delta, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff:
        value = _mapping(value, "observability bundle catalog entry diff")
        _strict(value, set(cls.FIELDS), "observability bundle catalog entry diff")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog entry diff is missing fields: {missing}")
        left = None if value["left_entry"] is None else catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry.from_mapping(value["left_entry"])
        right = None if value["right_entry"] is None else catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry.from_mapping(value["right_entry"])
        return cls(value["label"], value["status"], left, right, _sequence(value["changed_fields"], "observability bundle catalog entry diff changed fields", len(COMPARABLE_FIELDS)), value["accepted_delta"], value["ready_delta"], value["artifact_count_delta"], value["content_address"])


def _entry_diff_address_body(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff) -> dict[str, Any]:
    body = value.to_dict()
    body["content_address"] = None
    return body


def address_entry_diff(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff):
        raise ValidationError("observability bundle catalog entry diff address requires a typed entry diff")
    return content_hash(_entry_diff_address_body(value), prefix=ENTRY_DIFF_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff:
    """Addressed comparison of two verified observability-bundle catalogs."""

    FIELDS = (
        "diff_id",
        "left_catalog_id",
        "right_catalog_id",
        "left_catalog_address",
        "right_catalog_address",
        "left_entry_count",
        "right_entry_count",
        "entry_count_delta",
        "left_accepted_count",
        "right_accepted_count",
        "accepted_count_delta",
        "left_ready_count",
        "right_ready_count",
        "ready_count_delta",
        "left_rejected_count",
        "right_rejected_count",
        "rejected_count_delta",
        "left_artifact_count",
        "right_artifact_count",
        "artifact_count_delta",
        "added_labels",
        "removed_labels",
        "changed_labels",
        "unchanged_labels",
        "item_count",
        "added_count",
        "removed_count",
        "changed_count",
        "unchanged_count",
        "state",
        "items",
        "content_address",
    )

    def __init__(self, diff_id: str, left_catalog_id: str, right_catalog_id: str, left_catalog_address: str, right_catalog_address: str, left_entry_count: int, right_entry_count: int, entry_count_delta: int, left_accepted_count: int, right_accepted_count: int, accepted_count_delta: int, left_ready_count: int, right_ready_count: int, ready_count_delta: int, left_rejected_count: int, right_rejected_count: int, rejected_count_delta: int, left_artifact_count: int, right_artifact_count: int, artifact_count_delta: int, added_labels: Sequence[str], removed_labels: Sequence[str], changed_labels: Sequence[str], unchanged_labels: Sequence[str], item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, state: str, items: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff], content_address: str) -> None:
        self.diff_id = _label(diff_id, "observability bundle catalog diff ID")
        self.left_catalog_id = _label(left_catalog_id, "observability bundle catalog diff left catalog ID")
        self.right_catalog_id = _label(right_catalog_id, "observability bundle catalog diff right catalog ID")
        self.left_catalog_address = _address(left_catalog_address, "observability bundle catalog diff left catalog address", catalog_model.CATALOG_PREFIX)
        self.right_catalog_address = _address(right_catalog_address, "observability bundle catalog diff right catalog address", catalog_model.CATALOG_PREFIX)
        self.left_entry_count = _count(left_entry_count, "observability bundle catalog diff left entry count", catalog_model.MAX_ENTRIES)
        self.right_entry_count = _count(right_entry_count, "observability bundle catalog diff right entry count", catalog_model.MAX_ENTRIES)
        self.entry_count_delta = _delta(entry_count_delta, "observability bundle catalog diff entry count delta")
        self.left_accepted_count = _count(left_accepted_count, "observability bundle catalog diff left accepted count", catalog_model.MAX_ENTRIES)
        self.right_accepted_count = _count(right_accepted_count, "observability bundle catalog diff right accepted count", catalog_model.MAX_ENTRIES)
        self.accepted_count_delta = _delta(accepted_count_delta, "observability bundle catalog diff accepted count delta")
        self.left_ready_count = _count(left_ready_count, "observability bundle catalog diff left ready count", catalog_model.MAX_ENTRIES)
        self.right_ready_count = _count(right_ready_count, "observability bundle catalog diff right ready count", catalog_model.MAX_ENTRIES)
        self.ready_count_delta = _delta(ready_count_delta, "observability bundle catalog diff ready count delta")
        self.left_rejected_count = _count(left_rejected_count, "observability bundle catalog diff left rejected count", catalog_model.MAX_ENTRIES)
        self.right_rejected_count = _count(right_rejected_count, "observability bundle catalog diff right rejected count", catalog_model.MAX_ENTRIES)
        self.rejected_count_delta = _delta(rejected_count_delta, "observability bundle catalog diff rejected count delta")
        self.left_artifact_count = _count(left_artifact_count, "observability bundle catalog diff left artifact count", MAX_ARTIFACTS)
        self.right_artifact_count = _count(right_artifact_count, "observability bundle catalog diff right artifact count", MAX_ARTIFACTS)
        self.artifact_count_delta = _delta(artifact_count_delta, "observability bundle catalog diff artifact count delta", MAX_ARTIFACTS)
        self.added_labels = tuple(_label(item, "observability bundle catalog diff added label") for item in added_labels)
        self.removed_labels = tuple(_label(item, "observability bundle catalog diff removed label") for item in removed_labels)
        self.changed_labels = tuple(_label(item, "observability bundle catalog diff changed label") for item in changed_labels)
        self.unchanged_labels = tuple(_label(item, "observability bundle catalog diff unchanged label") for item in unchanged_labels)
        self.item_count = _count(item_count, "observability bundle catalog diff item count", MAX_ITEMS)
        self.added_count = _count(added_count, "observability bundle catalog diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "observability bundle catalog diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "observability bundle catalog diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "observability bundle catalog diff unchanged count", MAX_ITEMS)
        self.state = _text(state, "observability bundle catalog diff state", 32)
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if any(not isinstance(item, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff) for item in self.items):
            raise ValidationError("observability bundle catalog diff items must be typed")
        for name, values in (("added", self.added_labels), ("removed", self.removed_labels), ("changed", self.changed_labels), ("unchanged", self.unchanged_labels)):
            if tuple(values) != tuple(sorted(set(values))):
                raise ValidationError(f"observability bundle catalog diff {name} labels are not canonical")
        status_values = {status: tuple(item.label for item in self.items if item.status == status) for status in STATUSES}
        if (self.added_labels, self.removed_labels, self.changed_labels, self.unchanged_labels) != tuple(status_values[status] for status in STATUSES):
            raise ValidationError("observability bundle catalog diff status labels do not reconcile")
        if self.item_count != len(self.items) or self.item_count != sum(len(values) for values in status_values.values()) or self.item_count > MAX_ITEMS:
            raise ValidationError("observability bundle catalog diff item count is not conserved")
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != tuple(len(status_values[status]) for status in STATUSES):
            raise ValidationError("observability bundle catalog diff status counts are not conserved")
        if tuple(item.label for item in self.items) != tuple(sorted(item.label for item in self.items)) or len({item.label for item in self.items}) != self.item_count:
            raise ValidationError("observability bundle catalog diff item labels are not sorted and unique")
        if self.entry_count_delta != self.right_entry_count - self.left_entry_count or self.accepted_count_delta != self.right_accepted_count - self.left_accepted_count or self.ready_count_delta != self.right_ready_count - self.left_ready_count or self.rejected_count_delta != self.right_rejected_count - self.left_rejected_count or self.artifact_count_delta != self.right_artifact_count - self.left_artifact_count:
            raise ValidationError("observability bundle catalog diff aggregate deltas are not derived")
        if self.left_entry_count != self.left_accepted_count + self.left_rejected_count or self.right_entry_count != self.right_accepted_count + self.right_rejected_count:
            raise ValidationError("observability bundle catalog diff source denominators are not conserved")
        if self.left_artifact_count != self.left_entry_count * len(catalog_model.bundle_model.ARTIFACT_FILES) or self.right_artifact_count != self.right_entry_count * len(catalog_model.bundle_model.ARTIFACT_FILES):
            raise ValidationError("observability bundle catalog diff artifact totals are not conserved")
        expected_state = _state(self.added_count, self.removed_count, self.changed_count)
        if self.state not in STATES or self.state != expected_state:
            raise ValidationError("observability bundle catalog diff state is not derived")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog diff content address")
        else:
            _address(self.content_address, "observability bundle catalog diff content address", DIFF_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_diff(self) != self.content_address):
            raise ValidationError("observability bundle catalog diff address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "left_catalog_id": self.left_catalog_id, "right_catalog_id": self.right_catalog_id, "left_catalog_address": self.left_catalog_address, "right_catalog_address": self.right_catalog_address, "left_entry_count": self.left_entry_count, "right_entry_count": self.right_entry_count, "entry_count_delta": self.entry_count_delta, "left_accepted_count": self.left_accepted_count, "right_accepted_count": self.right_accepted_count, "accepted_count_delta": self.accepted_count_delta, "left_ready_count": self.left_ready_count, "right_ready_count": self.right_ready_count, "ready_count_delta": self.ready_count_delta, "left_rejected_count": self.left_rejected_count, "right_rejected_count": self.right_rejected_count, "rejected_count_delta": self.rejected_count_delta, "left_artifact_count": self.left_artifact_count, "right_artifact_count": self.right_artifact_count, "artifact_count_delta": self.artifact_count_delta, "added_labels": self.added_labels, "removed_labels": self.removed_labels, "changed_labels": self.changed_labels, "unchanged_labels": self.unchanged_labels, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "state": self.state, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS if key != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff:
        value = _mapping(value, "observability bundle catalog diff")
        _strict(value, set(cls.FIELDS), "observability bundle catalog diff")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog diff is missing fields: {missing}")
        items = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff.from_mapping(item) for item in _sequence(value["items"], "observability bundle catalog diff items", MAX_ITEMS))
        return cls(value["diff_id"], value["left_catalog_id"], value["right_catalog_id"], value["left_catalog_address"], value["right_catalog_address"], value["left_entry_count"], value["right_entry_count"], value["entry_count_delta"], value["left_accepted_count"], value["right_accepted_count"], value["accepted_count_delta"], value["left_ready_count"], value["right_ready_count"], value["ready_count_delta"], value["left_rejected_count"], value["right_rejected_count"], value["rejected_count_delta"], value["left_artifact_count"], value["right_artifact_count"], value["artifact_count_delta"], _sequence(value["added_labels"], "observability bundle catalog diff added labels", MAX_ITEMS), _sequence(value["removed_labels"], "observability bundle catalog diff removed labels", MAX_ITEMS), _sequence(value["changed_labels"], "observability bundle catalog diff changed labels", MAX_ITEMS), _sequence(value["unchanged_labels"], "observability bundle catalog diff unchanged labels", MAX_ITEMS), value["item_count"], value["added_count"], value["removed_count"], value["changed_count"], value["unchanged_count"], value["state"], items, value["content_address"])


def _state(added: int, removed: int, changed: int) -> str:
    if not added and not removed and not changed:
        return "unchanged"
    if added and not removed and not changed:
        return "added"
    if removed and not added and not changed:
        return "removed"
    if changed and not added and not removed:
        return "changed"
    return "mixed"


def _address_body(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff) -> dict[str, Any]:
    body = value.to_dict()
    body["content_address"] = None
    return body


def address_diff(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff):
        raise ValidationError("observability bundle catalog diff address requires a typed diff")
    return content_hash(_address_body(value), prefix=DIFF_PREFIX)


def _as_catalog(value: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog | Mapping[str, Any] | str | Path) -> catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog:
    if isinstance(value, catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog):
        return catalog_model.verify_catalog(value)
    if isinstance(value, (str, Path)):
        raise ValidationError("observability bundle catalog diff paths must be loaded into a catalog explicitly")
    return catalog_model.catalog_from_mapping(_mapping(value, "observability bundle catalog diff catalog"))


def _build_entry_diff(label: str, left: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry | None, right: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry | None) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff:
    if left is None:
        status = "added"
        fields: tuple[str, ...] = ()
    elif right is None:
        status = "removed"
        fields = ()
    else:
        left_projection = _projection(left)
        right_projection = _projection(right)
        fields = tuple(sorted(field for field in COMPARABLE_FIELDS if left_projection[field] != right_projection[field]))
        status = "changed" if fields else "unchanged"
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff(label, status, left, right, fields, _accepted(right) - _accepted(left), _ready(right) - _ready(left), _entry_delta(left, right, "artifact_count"), "pending:observability-bundle-catalog-entry-diff")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff(provisional.label, provisional.status, provisional.left_entry, provisional.right_entry, provisional.changed_fields, provisional.accepted_delta, provisional.ready_delta, provisional.artifact_count_delta, address_entry_diff(provisional))


def build_diff(left: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog | Mapping[str, Any], right: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog | Mapping[str, Any], *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff:
    """Compare two verified catalogs by stable public label."""

    left_catalog = _as_catalog(left)
    right_catalog = _as_catalog(right)
    left_entries = {entry.label: entry for entry in left_catalog.entries}
    right_entries = {entry.label: entry for entry in right_catalog.entries}
    items = tuple(_build_entry_diff(label, left_entries.get(label), right_entries.get(label)) for label in sorted(set(left_entries) | set(right_entries)))
    by_status = {status: tuple(item.label for item in items if item.status == status) for status in STATUSES}
    body = {"diff_id": _label(diff_id, "observability bundle catalog diff ID"), "left_catalog_id": left_catalog.catalog_id, "right_catalog_id": right_catalog.catalog_id, "left_catalog_address": left_catalog.content_address, "right_catalog_address": right_catalog.content_address, "left_entry_count": left_catalog.entry_count, "right_entry_count": right_catalog.entry_count, "entry_count_delta": right_catalog.entry_count - left_catalog.entry_count, "left_accepted_count": left_catalog.accepted_count, "right_accepted_count": right_catalog.accepted_count, "accepted_count_delta": right_catalog.accepted_count - left_catalog.accepted_count, "left_ready_count": left_catalog.ready_count, "right_ready_count": right_catalog.ready_count, "ready_count_delta": right_catalog.ready_count - left_catalog.ready_count, "left_rejected_count": left_catalog.rejected_count, "right_rejected_count": right_catalog.rejected_count, "rejected_count_delta": right_catalog.rejected_count - left_catalog.rejected_count, "left_artifact_count": left_catalog.entry_count * len(catalog_model.bundle_model.ARTIFACT_FILES), "right_artifact_count": right_catalog.entry_count * len(catalog_model.bundle_model.ARTIFACT_FILES), "artifact_count_delta": (right_catalog.entry_count - left_catalog.entry_count) * len(catalog_model.bundle_model.ARTIFACT_FILES), "added_labels": by_status["added"], "removed_labels": by_status["removed"], "changed_labels": by_status["changed"], "unchanged_labels": by_status["unchanged"], "item_count": len(items), "added_count": len(by_status["added"]), "removed_count": len(by_status["removed"]), "changed_count": len(by_status["changed"]), "unchanged_count": len(by_status["unchanged"]), "state": _state(len(by_status["added"]), len(by_status["removed"]), len(by_status["changed"])), "items": items}
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff(**body, content_address="pending:observability-bundle-catalog-diff")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff(**body, content_address=address_diff(provisional))


def diff_catalogs(left: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog | Mapping[str, Any], right: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog | Mapping[str, Any], *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff:
    return build_diff(left, right, diff_id=diff_id)


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff:
    return verify_diff(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff.from_mapping(value))


def verify_diff(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff):
        raise ValidationError("observability bundle catalog diff verification requires a typed diff")
    value._validate()
    if address_diff(value) != value.content_address:
        raise ValidationError("observability bundle catalog diff content address does not replay")
    return value


def diff_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff) -> str:
    value = verify_diff(value)
    output = io.StringIO()
    fields = ("label", "status", "changed_fields", "accepted_delta", "ready_delta", "artifact_count_delta", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        writer.writerow({"label": item.label, "status": item.status, "changed_fields": canonical_json(item.changed_fields), "accepted_delta": item.accepted_delta, "ready_delta": item.ready_delta, "artifact_count_delta": item.artifact_count_delta, "content_address": item.content_address})
    return output.getvalue()


def render_diff_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff) -> str:
    value = verify_diff(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Diff", "", f"- State: `{value.state}`", f"- Left catalog: `{value.left_catalog_id}`", f"- Right catalog: `{value.right_catalog_id}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Unchanged: `{value.unchanged_count}`", f"- Entry delta: `{value.entry_count_delta:+d}`", f"- Accepted delta: `{value.accepted_count_delta:+d}`", f"- Ready delta: `{value.ready_count_delta:+d}`", f"- Artifact delta: `{value.artifact_count_delta:+d}`", f"- Content address: `{value.content_address}`", "", "| label | status | changed fields | accepted Δ | ready Δ | artifacts Δ |", "| --- | --- | --- | ---: | ---: | ---: |"]
    lines.extend(f"| `{item.label}` | `{item.status}` | `{', '.join(item.changed_fields) or 'none'}` | `{item.accepted_delta:+d}` | `{item.ready_delta:+d}` | `{item.artifact_count_delta:+d}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def entry_diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff.FIELDS), "properties": {"label": {"type": "string", "maxLength": 128}, "status": {"type": "string", "enum": list(STATUSES)}, "left_entry": {"anyOf": [catalog_model.entry_schema(), {"type": "null"}]}, "right_entry": {"anyOf": [catalog_model.entry_schema(), {"type": "null"}]}, "changed_fields": {"type": "array", "items": {"type": "string", "enum": list(COMPARABLE_FIELDS)}, "maxItems": len(COMPARABLE_FIELDS)}, "accepted_delta": {"type": "integer", "minimum": -1, "maximum": 1}, "ready_delta": {"type": "integer", "minimum": -1, "maximum": 1}, "artifact_count_delta": {"type": "integer", "minimum": -len(catalog_model.bundle_model.ARTIFACT_FILES), "maximum": len(catalog_model.bundle_model.ARTIFACT_FILES)}, "content_address": {"type": "string", "pattern": "^" + ENTRY_DIFF_PREFIX + ":"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff.FIELDS), "properties": {"diff_id": {"type": "string", "maxLength": 128}, "left_catalog_id": {"type": "string", "maxLength": 128}, "right_catalog_id": {"type": "string", "maxLength": 128}, "left_catalog_address": {"type": "string", "pattern": "^" + catalog_model.CATALOG_PREFIX + ":"}, "right_catalog_address": {"type": "string", "pattern": "^" + catalog_model.CATALOG_PREFIX + ":"}, **{field: {"type": "integer", "minimum": 0, "maximum": catalog_model.MAX_ENTRIES} for field in ("left_entry_count", "right_entry_count", "left_accepted_count", "right_accepted_count", "left_ready_count", "right_ready_count", "left_rejected_count", "right_rejected_count")}, **{field: {"type": "integer", "minimum": 0, "maximum": MAX_ARTIFACTS} for field in ("left_artifact_count", "right_artifact_count")}, **{field: {"type": "integer", "minimum": -MAX_ARTIFACTS, "maximum": MAX_ARTIFACTS} for field in ("entry_count_delta", "accepted_count_delta", "ready_count_delta", "rejected_count_delta", "artifact_count_delta")}, **{field: {"type": "array", "items": {"type": "string", "maxLength": 128}, "maxItems": MAX_ITEMS} for field in ("added_labels", "removed_labels", "changed_labels", "unchanged_labels")}, "item_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "added_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "removed_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "changed_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "unchanged_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "state": {"type": "string", "enum": list(STATES)}, "items": {"type": "array", "maxItems": MAX_ITEMS, "items": entry_diff_schema()}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "entry_diff_prefix": ENTRY_DIFF_PREFIX, "statuses": STATUSES, "states": STATES, "comparable_fields": COMPARABLE_FIELDS, "limits": {"max_catalog_entries": catalog_model.MAX_ENTRIES, "max_items": MAX_ITEMS, "max_artifacts": MAX_ARTIFACTS}, "features": ("verified catalog mapping inputs", "stable label-keyed comparison", "added removed changed and unchanged classifications", "semantic field transitions", "acceptance readiness and rejection denominator deltas", "artifact-total conservation", "addressed entry diffs", "aggregate state classification", "content-addressed replay", "path-free JSON CSV and Markdown exports"), "schemas": ("entry-diff", "diff")}


__all__ = [
    "BOUNDARY",
    "COMPARABLE_FIELDS",
    "DEFAULT_DIFF_ID",
    "DIFF_PREFIX",
    "ENTRY_DIFF_PREFIX",
    "MAX_ARTIFACTS",
    "MAX_ITEMS",
    "STATES",
    "STATUSES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff",
    "address_diff",
    "address_entry_diff",
    "build_diff",
    "capabilities",
    "diff_catalogs",
    "diff_csv",
    "diff_from_mapping",
    "diff_json",
    "diff_schema",
    "entry_diff_schema",
    "render_diff_markdown",
    "verify_diff",
]
