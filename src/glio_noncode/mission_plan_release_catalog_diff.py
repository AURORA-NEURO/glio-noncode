"""Deterministic evolution diffs for public mission-plan release catalogs.

Catalogs provide a stable inventory; this module explains how one inventory
changed into another.  The diff is keyed by public release ID and compares
only the aggregate catalog entry fields.  Added, removed, changed, and
unchanged entries remain explicit, and aggregate deltas make review and
automation possible without reopening any mission planner.

The implementation is deliberately address-oriented.  Inputs may be typed
catalogs, catalog bundles, verified offline directories, or public catalog
JSON mappings.  Outputs contain no source payloads, request text, routing
identifiers, attribution, language, model, producer, or identity metadata.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog import (
    MissionPlanReleaseCatalog,
    MissionPlanReleaseCatalogBundle,
    MissionPlanReleaseCatalogEntry,
    MissionPlanReleaseCatalogOffline,
    load_mission_plan_release_catalog,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_CATALOG_DIFF_VERSION = "mission-plan-release-catalog-diff-v1"
MISSION_PLAN_RELEASE_CATALOG_DIFF_SCHEMA_VERSION = "mission-plan-release-catalog-diff-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_DIFF_CAPABILITIES_VERSION = "mission-plan-release-catalog-diff-capabilities-v1"


class MissionPlanReleaseCatalogDiffStatus(StrEnum):
    """Stable classification of one release ID across two catalogs."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _catalog(value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path) -> MissionPlanReleaseCatalog:
    if isinstance(value, MissionPlanReleaseCatalog):
        return value
    if isinstance(value, MissionPlanReleaseCatalogBundle):
        return value.catalog
    if isinstance(value, MissionPlanReleaseCatalogOffline):
        return value.catalog
    if isinstance(value, (str, Path)):
        return load_mission_plan_release_catalog(value).catalog
    body = dict(value)
    if "catalog" in body and isinstance(body["catalog"], Mapping):
        body = dict(body["catalog"])
    return MissionPlanReleaseCatalog.from_mapping(body)


_COMPARABLE_FIELDS = (
    "release_address",
    "plan_id",
    "plan_address",
    "state",
    "decision",
    "accepted",
    "step_count",
    "optional_step_count",
    "deterministic_step_count",
    "network_step_count",
    "artifact_count",
    "check_count",
    "warning_count",
    "workflow_kinds",
)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogEntryDiff:
    """Public comparison for one release ID."""

    release_id: str
    status: MissionPlanReleaseCatalogDiffStatus
    left_entry: MissionPlanReleaseCatalogEntry | None
    right_entry: MissionPlanReleaseCatalogEntry | None
    changed_fields: tuple[str, ...]
    step_count_delta: int
    optional_step_count_delta: int
    deterministic_step_count_delta: int
    network_step_count_delta: int
    artifact_count_delta: int
    check_count_delta: int
    warning_count_delta: int
    content_address: str

    def __post_init__(self) -> None:
        _text(self.release_id, "catalog_entry_diff.release_id")
        if self.left_entry is None and self.right_entry is None:
            raise ValidationError("catalog entry diff requires a left or right entry")
        if self.status is MissionPlanReleaseCatalogDiffStatus.ADDED and self.left_entry is not None:
            raise ValidationError("added catalog entry cannot have a left entry")
        if self.status is MissionPlanReleaseCatalogDiffStatus.REMOVED and self.right_entry is not None:
            raise ValidationError("removed catalog entry cannot have a right entry")
        if self.status is MissionPlanReleaseCatalogDiffStatus.UNCHANGED and self.changed_fields:
            raise ValidationError("unchanged catalog entry cannot have changed fields")
        _text(self.content_address, "catalog_entry_diff.content_address")

    def to_dict(self) -> dict[str, Any]:
        body = {
            "release_id": self.release_id,
            "status": self.status,
            "left_entry": None if self.left_entry is None else self.left_entry.to_dict(),
            "right_entry": None if self.right_entry is None else self.right_entry.to_dict(),
            "changed_fields": list(self.changed_fields),
            "step_count_delta": self.step_count_delta,
            "optional_step_count_delta": self.optional_step_count_delta,
            "deterministic_step_count_delta": self.deterministic_step_count_delta,
            "network_step_count_delta": self.network_step_count_delta,
            "artifact_count_delta": self.artifact_count_delta,
            "check_count_delta": self.check_count_delta,
            "warning_count_delta": self.warning_count_delta,
        }
        return jsonable(body | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogDiff:
    """Addressed comparison of two public release catalogs."""

    diff_version: str
    left_catalog_id: str
    right_catalog_id: str
    left_catalog_address: str
    right_catalog_address: str
    added_release_ids: tuple[str, ...]
    removed_release_ids: tuple[str, ...]
    changed_release_ids: tuple[str, ...]
    unchanged_release_ids: tuple[str, ...]
    entry_diffs: tuple[MissionPlanReleaseCatalogEntryDiff, ...]
    aggregate_delta: Mapping[str, int]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.diff_version != MISSION_PLAN_RELEASE_CATALOG_DIFF_VERSION:
            raise ValidationError("catalog diff version is invalid")
        for field in (
            "left_catalog_id",
            "right_catalog_id",
            "left_catalog_address",
            "right_catalog_address",
            "content_address",
        ):
            _text(getattr(self, field), f"catalog_diff.{field}")
        for field in (
            "added_release_ids",
            "removed_release_ids",
            "changed_release_ids",
            "unchanged_release_ids",
        ):
            values = getattr(self, field)
            if tuple(values) != tuple(sorted(set(values))):
                raise ValidationError(f"catalog_diff.{field} must be unique and sorted")
        if len(self.entry_diffs) != sum(
            len(getattr(self, field))
            for field in (
                "added_release_ids",
                "removed_release_ids",
                "changed_release_ids",
                "unchanged_release_ids",
            )
        ):
            raise ValidationError("catalog diff entry classifications do not reconcile")

    @property
    def added_count(self) -> int:
        return len(self.added_release_ids)

    @property
    def removed_count(self) -> int:
        return len(self.removed_release_ids)

    @property
    def changed_count(self) -> int:
        return len(self.changed_release_ids)

    @property
    def unchanged_count(self) -> int:
        return len(self.unchanged_release_ids)

    def to_dict(self) -> dict[str, Any]:
        body = {
            "diff_version": self.diff_version,
            "left_catalog_id": self.left_catalog_id,
            "right_catalog_id": self.right_catalog_id,
            "left_catalog_address": self.left_catalog_address,
            "right_catalog_address": self.right_catalog_address,
            "added_release_ids": list(self.added_release_ids),
            "removed_release_ids": list(self.removed_release_ids),
            "changed_release_ids": list(self.changed_release_ids),
            "unchanged_release_ids": list(self.unchanged_release_ids),
            "entry_diffs": self.entry_diffs,
            "aggregate_delta": dict(self.aggregate_delta),
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _entry_diff(
    release_id: str,
    left: MissionPlanReleaseCatalogEntry | None,
    right: MissionPlanReleaseCatalogEntry | None,
) -> MissionPlanReleaseCatalogEntryDiff:
    if left is None:
        status = MissionPlanReleaseCatalogDiffStatus.ADDED
        changed: tuple[str, ...] = ()
    elif right is None:
        status = MissionPlanReleaseCatalogDiffStatus.REMOVED
        changed = ()
    else:
        changed = tuple(field for field in _COMPARABLE_FIELDS if getattr(left, field) != getattr(right, field))
        status = MissionPlanReleaseCatalogDiffStatus.CHANGED if changed else MissionPlanReleaseCatalogDiffStatus.UNCHANGED

    def delta(field: str) -> int:
        left_value = 0 if left is None else int(getattr(left, field))
        right_value = 0 if right is None else int(getattr(right, field))
        return right_value - left_value

    body = {
        "release_id": release_id,
        "status": status,
        "left_entry": left,
        "right_entry": right,
        "changed_fields": changed,
        "step_count_delta": delta("step_count"),
        "optional_step_count_delta": delta("optional_step_count"),
        "deterministic_step_count_delta": delta("deterministic_step_count"),
        "network_step_count_delta": delta("network_step_count"),
        "artifact_count_delta": delta("artifact_count"),
        "check_count_delta": delta("check_count"),
        "warning_count_delta": delta("warning_count"),
    }
    return MissionPlanReleaseCatalogEntryDiff(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-entry-diff"),
    )


def _aggregate(catalog: MissionPlanReleaseCatalog) -> dict[str, int]:
    return {
        "entry_count": catalog.entry_count,
        "accepted_entry_count": catalog.accepted_entry_count,
        "rejected_entry_count": catalog.rejected_entry_count,
        "step_count": sum(item.step_count for item in catalog.entries),
        "optional_step_count": sum(item.optional_step_count for item in catalog.entries),
        "deterministic_step_count": sum(item.deterministic_step_count for item in catalog.entries),
        "network_step_count": sum(item.network_step_count for item in catalog.entries),
        "artifact_count": sum(item.artifact_count for item in catalog.entries),
        "check_count": sum(item.check_count for item in catalog.entries),
        "warning_count": sum(item.warning_count for item in catalog.entries),
    }


def diff_mission_plan_release_catalogs(
    left: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
    right: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseCatalogDiff:
    """Compare two public release catalogs in stable release-ID order."""

    left_catalog = _catalog(left)
    right_catalog = _catalog(right)
    left_entries = {item.release_id: item for item in left_catalog.entries}
    right_entries = {item.release_id: item for item in right_catalog.entries}
    release_ids = tuple(sorted(set(left_entries) | set(right_entries)))
    entry_diffs = tuple(_entry_diff(item, left_entries.get(item), right_entries.get(item)) for item in release_ids)
    added = tuple(item.release_id for item in entry_diffs if item.status is MissionPlanReleaseCatalogDiffStatus.ADDED)
    removed = tuple(item.release_id for item in entry_diffs if item.status is MissionPlanReleaseCatalogDiffStatus.REMOVED)
    changed = tuple(item.release_id for item in entry_diffs if item.status is MissionPlanReleaseCatalogDiffStatus.CHANGED)
    unchanged = tuple(item.release_id for item in entry_diffs if item.status is MissionPlanReleaseCatalogDiffStatus.UNCHANGED)
    left_aggregate = _aggregate(left_catalog)
    right_aggregate = _aggregate(right_catalog)
    aggregate_delta = {key: right_aggregate[key] - left_aggregate[key] for key in left_aggregate}
    body = {
        "diff_version": MISSION_PLAN_RELEASE_CATALOG_DIFF_VERSION,
        "left_catalog_id": left_catalog.catalog_id,
        "right_catalog_id": right_catalog.catalog_id,
        "left_catalog_address": left_catalog.content_address,
        "right_catalog_address": right_catalog.content_address,
        "added_release_ids": added,
        "removed_release_ids": removed,
        "changed_release_ids": changed,
        "unchanged_release_ids": unchanged,
        "entry_diffs": entry_diffs,
        "aggregate_delta": aggregate_delta,
        "accepted": left_catalog.accepted and right_catalog.accepted,
    }
    return MissionPlanReleaseCatalogDiff(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-diff"),
    )


def mission_plan_release_catalog_diff_json(value: MissionPlanReleaseCatalogDiff) -> str:
    """Render a catalog diff as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def mission_plan_release_catalog_diff_csv(value: MissionPlanReleaseCatalogDiff) -> str:
    """Render one deterministic row per release comparison."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "release_id",
            "status",
            "changed_fields",
            "step_count_delta",
            "optional_step_count_delta",
            "deterministic_step_count_delta",
            "network_step_count_delta",
            "artifact_count_delta",
            "check_count_delta",
            "warning_count_delta",
            "content_address",
        )
    )
    for item in value.entry_diffs:
        writer.writerow(
            (
                item.release_id,
                item.status,
                "|".join(item.changed_fields),
                item.step_count_delta,
                item.optional_step_count_delta,
                item.deterministic_step_count_delta,
                item.network_step_count_delta,
                item.artifact_count_delta,
                item.check_count_delta,
                item.warning_count_delta,
                item.content_address,
            )
        )
    return output.getvalue()


def mission_plan_release_catalog_diff_markdown(value: MissionPlanReleaseCatalogDiff) -> str:
    """Render a catalog diff as a review table."""

    lines = [
        "# Mission plan release catalog diff",
        "",
        f"- Left: `{value.left_catalog_id}`",
        f"- Right: `{value.right_catalog_id}`",
        f"- Added: `{value.added_count}`",
        f"- Removed: `{value.removed_count}`",
        f"- Changed: `{value.changed_count}`",
        f"- Unchanged: `{value.unchanged_count}`",
        "",
        "| Release | Status | Changed fields | Steps Δ | Warnings Δ |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    lines.extend(
        f"| `{item.release_id}` | `{item.status.value}` | `{', '.join(item.changed_fields) or 'none'}` | "
        f"{item.step_count_delta:+d} | {item.warning_count_delta:+d} |"
        for item in value.entry_diffs
    )
    return "\n".join(lines) + "\n"


def mission_plan_release_catalog_diff_export_payloads(
    value: MissionPlanReleaseCatalogDiff,
) -> dict[str, str]:
    """Return deterministic catalog-diff projections."""

    return {
        "mission-plan-release-catalog-diff.json": mission_plan_release_catalog_diff_json(value),
        "mission-plan-release-catalog-diff.csv": mission_plan_release_catalog_diff_csv(value),
        "mission-plan-release-catalog-diff.md": mission_plan_release_catalog_diff_markdown(value),
    }


def mission_plan_release_catalog_diff_schema() -> dict[str, Any]:
    """Return the catalog diff contract."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_DIFF_SCHEMA_VERSION,
        "diff_version": MISSION_PLAN_RELEASE_CATALOG_DIFF_VERSION,
        "statuses": [item.value for item in MissionPlanReleaseCatalogDiffStatus],
        "entry_diff_fields": [
            "release_id",
            "status",
            "left_entry",
            "right_entry",
            "changed_fields",
            "step_count_delta",
            "optional_step_count_delta",
            "deterministic_step_count_delta",
            "network_step_count_delta",
            "artifact_count_delta",
            "check_count_delta",
            "warning_count_delta",
            "content_address",
        ],
        "aggregate_delta_fields": list(_aggregate(MissionPlanReleaseCatalog("mission-plan-release-catalog-v1", "schema", (), True, "x")).keys()),
        "ordering": "release ID ascending",
        "timestamp_free": True,
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_catalog_diff_capabilities() -> dict[str, Any]:
    """Return catalog diff capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_DIFF_CAPABILITIES_VERSION,
        "added_removed_changed_unchanged": True,
        "aggregate_deltas": True,
        "addressed_entry_diffs": True,
        "verified_offline_input": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
        "timestamp_free": True,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_DIFF_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_DIFF_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_DIFF_VERSION",
    "MissionPlanReleaseCatalogDiff",
    "MissionPlanReleaseCatalogDiffStatus",
    "MissionPlanReleaseCatalogEntryDiff",
    "diff_mission_plan_release_catalogs",
    "mission_plan_release_catalog_diff_capabilities",
    "mission_plan_release_catalog_diff_csv",
    "mission_plan_release_catalog_diff_export_payloads",
    "mission_plan_release_catalog_diff_json",
    "mission_plan_release_catalog_diff_markdown",
    "mission_plan_release_catalog_diff_schema",
]
