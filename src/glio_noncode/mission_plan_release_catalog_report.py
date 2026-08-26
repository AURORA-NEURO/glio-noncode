"""Deterministic aggregate reports for public mission-plan release catalogs.

A catalog answers which public releases exist.  A report answers what the
catalog contains at a glance without requiring a consumer to scan every row.
This module computes bounded distributions for release state, decision,
workflow kind, and aggregate size counters.  Counts are conserved, shares are
represented as integer basis points, and every bucket and the complete report
has a content address.

The report is a lossy public projection.  It never carries release payloads,
request text, routing identifiers, subject data, attribution, language,
model, producer, or identity metadata.  It is read-only and descriptive; it
does not execute workflows, reopen private planner state, or authorize a
clinical decision.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog import (
    MissionPlanReleaseCatalog,
    MissionPlanReleaseCatalogBundle,
    MissionPlanReleaseCatalogOffline,
    load_mission_plan_release_catalog,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_CATALOG_REPORT_VERSION = "mission-plan-release-catalog-report-v1"
MISSION_PLAN_RELEASE_CATALOG_REPORT_SCHEMA_VERSION = "mission-plan-release-catalog-report-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_REPORT_CAPABILITIES_VERSION = "mission-plan-release-catalog-report-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_REPORT_MAX_BUCKETS = 64
MISSION_PLAN_RELEASE_CATALOG_REPORT_SHARE_BASIS_POINTS = 10_000

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "contact",
        "email",
        "generated_by",
        "identity",
        "language",
        "model",
        "model_id",
        "patient",
        "producer",
        "programming_language",
        "raw_request",
        "request",
        "secret",
        "subject",
        "token",
        "tool_id",
    }
)


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): child for key, child in value.items()}


def _private_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                paths.append(child_path)
            paths.extend(_private_paths(child, child_path))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, child in enumerate(value):
            paths.extend(_private_paths(child, f"{path}[{index}]"))
        return tuple(paths)
    return ()


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogReportBucket:
    """One deterministic categorical distribution bucket."""

    bucket_key: str
    count: int
    share_basis_points: int
    content_address: str

    def __post_init__(self) -> None:
        _text(self.bucket_key, "catalog_report_bucket.bucket_key", maximum=180)
        if isinstance(self.count, bool) or not isinstance(self.count, int) or self.count < 0:
            raise ValidationError("catalog report bucket count must be a non-negative integer")
        if (
            isinstance(self.share_basis_points, bool)
            or not isinstance(self.share_basis_points, int)
            or not 0 <= self.share_basis_points <= MISSION_PLAN_RELEASE_CATALOG_REPORT_SHARE_BASIS_POINTS
        ):
            raise ValidationError("catalog report bucket share must be valid basis points")
        _text(self.content_address, "catalog_report_bucket.content_address")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogReportBucket":
        body = _mapping(value, "catalog report bucket")
        allowed = {"bucket_key", "count", "share_basis_points", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog report bucket contains unsupported fields: {sorted(unknown)}")
        try:
            count = int(body.get("count"))
            share = int(body.get("share_basis_points"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("catalog report bucket contains invalid integers") from exc
        bucket = cls(
            bucket_key=_text(body.get("bucket_key"), "catalog_report_bucket.bucket_key"),
            count=count,
            share_basis_points=share,
            content_address=_text(body.get("content_address"), "catalog_report_bucket.content_address"),
        )
        expected = content_hash(
            {
                "bucket_key": bucket.bucket_key,
                "count": bucket.count,
                "share_basis_points": bucket.share_basis_points,
            },
            prefix="mission-plan-release-catalog-report-bucket",
        )
        if bucket.content_address != expected:
            raise ValidationError("catalog report bucket content address does not reconcile")
        return bucket

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogReport:
    """Addressed aggregate report for one public release catalog."""

    report_version: str
    catalog_id: str
    catalog_address: str
    entry_count: int
    accepted_entry_count: int
    rejected_entry_count: int
    total_step_count: int
    total_optional_step_count: int
    total_deterministic_step_count: int
    total_network_step_count: int
    total_artifact_count: int
    total_check_count: int
    total_warning_count: int
    workflow_kind_count: int
    state_buckets: tuple[MissionPlanReleaseCatalogReportBucket, ...]
    decision_buckets: tuple[MissionPlanReleaseCatalogReportBucket, ...]
    workflow_buckets: tuple[MissionPlanReleaseCatalogReportBucket, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.report_version != MISSION_PLAN_RELEASE_CATALOG_REPORT_VERSION:
            raise ValidationError("catalog report version is invalid")
        _text(self.catalog_id, "catalog_report.catalog_id", maximum=96)
        _text(self.catalog_address, "catalog_report.catalog_address")
        _text(self.content_address, "catalog_report.content_address")
        for field in (
            "entry_count",
            "accepted_entry_count",
            "rejected_entry_count",
            "total_step_count",
            "total_optional_step_count",
            "total_deterministic_step_count",
            "total_network_step_count",
            "total_artifact_count",
            "total_check_count",
            "total_warning_count",
            "workflow_kind_count",
        ):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError(f"catalog_report.{field} must be a non-negative integer")
        if self.accepted_entry_count + self.rejected_entry_count != self.entry_count:
            raise ValidationError("catalog report acceptance counts do not reconcile")
        if self.total_optional_step_count > self.total_step_count:
            raise ValidationError("catalog report optional steps exceed total steps")
        if self.total_deterministic_step_count > self.total_step_count:
            raise ValidationError("catalog report deterministic steps exceed total steps")
        if self.total_network_step_count > self.total_step_count:
            raise ValidationError("catalog report network steps exceed total steps")
        for field in ("state_buckets", "decision_buckets", "workflow_buckets"):
            buckets = getattr(self, field)
            if len(buckets) > MISSION_PLAN_RELEASE_CATALOG_REPORT_MAX_BUCKETS:
                raise ValidationError(f"catalog report {field} exceed the bucket bound")
            keys = tuple(item.bucket_key for item in buckets)
            if keys != tuple(sorted(set(keys))):
                raise ValidationError(f"catalog report {field} must be unique and sorted")
            expected_count = self.workflow_kind_count if field == "workflow_buckets" else self.entry_count
            if sum(item.count for item in buckets) != expected_count:
                raise ValidationError(f"catalog report {field} counts do not reconcile")
            if sum(item.share_basis_points for item in buckets) > MISSION_PLAN_RELEASE_CATALOG_REPORT_SHARE_BASIS_POINTS:
                raise ValidationError(f"catalog report {field} shares exceed the basis-point bound")

    @property
    def state_counts(self) -> dict[str, int]:
        return {item.bucket_key: item.count for item in self.state_buckets}

    @property
    def decision_counts(self) -> dict[str, int]:
        return {item.bucket_key: item.count for item in self.decision_buckets}

    @property
    def workflow_counts(self) -> dict[str, int]:
        return {item.bucket_key: item.count for item in self.workflow_buckets}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogReport":
        body = _mapping(value, "mission plan release catalog report")
        allowed = {
            "report_version",
            "catalog_id",
            "catalog_address",
            "entry_count",
            "accepted_entry_count",
            "rejected_entry_count",
            "total_step_count",
            "total_optional_step_count",
            "total_deterministic_step_count",
            "total_network_step_count",
            "total_artifact_count",
            "total_check_count",
            "total_warning_count",
            "workflow_kind_count",
            "state_buckets",
            "decision_buckets",
            "workflow_buckets",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog report contains unsupported fields: {sorted(unknown)}")
        numeric_fields = (
            "entry_count",
            "accepted_entry_count",
            "rejected_entry_count",
            "total_step_count",
            "total_optional_step_count",
            "total_deterministic_step_count",
            "total_network_step_count",
            "total_artifact_count",
            "total_check_count",
            "total_warning_count",
            "workflow_kind_count",
        )
        try:
            numbers = {field: int(body.get(field)) for field in numeric_fields}
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("catalog report contains invalid totals") from exc
        bucket_values: dict[str, tuple[MissionPlanReleaseCatalogReportBucket, ...]] = {}
        for field in ("state_buckets", "decision_buckets", "workflow_buckets"):
            raw = body.get(field, ())
            if not isinstance(raw, (list, tuple)):
                raise ValidationError(f"catalog report {field} must be an array")
            bucket_values[field] = tuple(MissionPlanReleaseCatalogReportBucket.from_mapping(item) for item in raw)
        report = cls(
            report_version=_text(body.get("report_version"), "catalog_report.report_version"),
            catalog_id=_text(body.get("catalog_id"), "catalog_report.catalog_id", maximum=96),
            catalog_address=_text(body.get("catalog_address"), "catalog_report.catalog_address"),
            **numbers,
            state_buckets=bucket_values["state_buckets"],
            decision_buckets=bucket_values["decision_buckets"],
            workflow_buckets=bucket_values["workflow_buckets"],
            accepted=bool(body.get("accepted")),
            content_address=_text(body.get("content_address"), "catalog_report.content_address"),
        )
        expected = _report_address_body(report)
        if report.content_address != content_hash(expected, prefix="mission-plan-release-catalog-report"):
            raise ValidationError("catalog report content address does not reconcile")
        if bool(report.accepted) != bool(report.entry_count == report.accepted_entry_count):
            raise ValidationError("catalog report acceptance does not reconcile")
        if _private_paths(report.to_dict()):
            raise ValidationError("catalog report contains restricted metadata")
        return report

    def to_dict(self) -> dict[str, Any]:
        body = {
            "report_version": self.report_version,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "entry_count": self.entry_count,
            "accepted_entry_count": self.accepted_entry_count,
            "rejected_entry_count": self.rejected_entry_count,
            "total_step_count": self.total_step_count,
            "total_optional_step_count": self.total_optional_step_count,
            "total_deterministic_step_count": self.total_deterministic_step_count,
            "total_network_step_count": self.total_network_step_count,
            "total_artifact_count": self.total_artifact_count,
            "total_check_count": self.total_check_count,
            "total_warning_count": self.total_warning_count,
            "workflow_kind_count": self.workflow_kind_count,
            "state_buckets": self.state_buckets,
            "decision_buckets": self.decision_buckets,
            "workflow_buckets": self.workflow_buckets,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _report_address_body(report: MissionPlanReleaseCatalogReport) -> dict[str, Any]:
    return {
        "report_version": report.report_version,
        "catalog_id": report.catalog_id,
        "catalog_address": report.catalog_address,
        "entry_count": report.entry_count,
        "accepted_entry_count": report.accepted_entry_count,
        "rejected_entry_count": report.rejected_entry_count,
        "total_step_count": report.total_step_count,
        "total_optional_step_count": report.total_optional_step_count,
        "total_deterministic_step_count": report.total_deterministic_step_count,
        "total_network_step_count": report.total_network_step_count,
        "total_artifact_count": report.total_artifact_count,
        "total_check_count": report.total_check_count,
        "total_warning_count": report.total_warning_count,
        "workflow_kind_count": report.workflow_kind_count,
        "state_buckets": report.state_buckets,
        "decision_buckets": report.decision_buckets,
        "workflow_buckets": report.workflow_buckets,
        "accepted": report.accepted,
    }


def _as_catalog(
    value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseCatalog:
    if isinstance(value, MissionPlanReleaseCatalog):
        return value
    if isinstance(value, MissionPlanReleaseCatalogBundle):
        return value.catalog
    if isinstance(value, MissionPlanReleaseCatalogOffline):
        return value.catalog
    if isinstance(value, (str, Path)):
        return load_mission_plan_release_catalog(value).catalog
    body = _mapping(value, "catalog report source")
    if isinstance(body.get("catalog"), Mapping):
        body = _mapping(body["catalog"], "catalog report catalog")
    return MissionPlanReleaseCatalog.from_mapping(body)


def _bucket(key: str, count: int, total: int) -> MissionPlanReleaseCatalogReportBucket:
    body = {
        "bucket_key": _text(key, "catalog_report_bucket.bucket_key"),
        "count": count,
        "share_basis_points": 0
        if total == 0
        else min(
            MISSION_PLAN_RELEASE_CATALOG_REPORT_SHARE_BASIS_POINTS,
            count * MISSION_PLAN_RELEASE_CATALOG_REPORT_SHARE_BASIS_POINTS // total,
        ),
    }
    return MissionPlanReleaseCatalogReportBucket(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-report-bucket"),
    )


def _buckets(values: Mapping[str, int], total: int) -> tuple[MissionPlanReleaseCatalogReportBucket, ...]:
    if len(values) > MISSION_PLAN_RELEASE_CATALOG_REPORT_MAX_BUCKETS:
        raise ValidationError("catalog report distribution exceeds the bucket bound")
    return tuple(_bucket(key, int(values[key]), total) for key in sorted(values))


def build_mission_plan_release_catalog_report(
    value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseCatalogReport:
    """Build a deterministic aggregate report from a public catalog."""

    catalog = _as_catalog(value)
    states: dict[str, int] = {}
    decisions: dict[str, int] = {}
    workflows: dict[str, int] = {}
    totals = {
        "total_step_count": 0,
        "total_optional_step_count": 0,
        "total_deterministic_step_count": 0,
        "total_network_step_count": 0,
        "total_artifact_count": 0,
        "total_check_count": 0,
        "total_warning_count": 0,
        "workflow_kind_count": 0,
    }
    for entry in catalog.entries:
        states[entry.state] = states.get(entry.state, 0) + 1
        decisions[entry.decision] = decisions.get(entry.decision, 0) + 1
        for workflow_kind in entry.workflow_kinds:
            workflows[workflow_kind] = workflows.get(workflow_kind, 0) + 1
        totals["workflow_kind_count"] += len(entry.workflow_kinds)
        for field in (
            "total_step_count",
            "total_optional_step_count",
            "total_deterministic_step_count",
            "total_network_step_count",
            "total_artifact_count",
            "total_check_count",
            "total_warning_count",
        ):
            totals[field] += int(getattr(entry, field.removeprefix("total_")))
    report_body = {
        "report_version": MISSION_PLAN_RELEASE_CATALOG_REPORT_VERSION,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "entry_count": catalog.entry_count,
        "accepted_entry_count": catalog.accepted_entry_count,
        "rejected_entry_count": catalog.rejected_entry_count,
        **totals,
        "state_buckets": _buckets(states, catalog.entry_count),
        "decision_buckets": _buckets(decisions, catalog.entry_count),
        "workflow_buckets": _buckets(workflows, totals["workflow_kind_count"]),
        "accepted": catalog.accepted,
    }
    report = MissionPlanReleaseCatalogReport(
        **report_body,
        content_address=content_hash(report_body, prefix="mission-plan-release-catalog-report"),
    )
    if _private_paths(report.to_dict()):
        raise ValidationError("catalog report contains restricted metadata")
    if any(sum(item.count for item in buckets) != catalog.entry_count for buckets in (report.state_buckets, report.decision_buckets)):
        raise ValidationError("catalog report categorical counts do not reconcile")
    if sum(item.count for item in report.workflow_buckets) != report.workflow_kind_count:
        raise ValidationError("catalog report workflow counts do not reconcile")
    return report


def mission_plan_release_catalog_report_json(
    report: MissionPlanReleaseCatalogReport | Mapping[str, Any],
) -> str:
    """Return canonical JSON for a catalog report."""

    value = report if isinstance(report, MissionPlanReleaseCatalogReport) else MissionPlanReleaseCatalogReport.from_mapping(report)
    return canonical_json(value.to_dict())


def mission_plan_release_catalog_report_csv(
    report: MissionPlanReleaseCatalogReport | Mapping[str, Any],
) -> str:
    """Return a stable bucket-level CSV report."""

    value = report if isinstance(report, MissionPlanReleaseCatalogReport) else MissionPlanReleaseCatalogReport.from_mapping(report)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("bucket_kind", "bucket_key", "count", "share_basis_points"))
    for kind, buckets in (
        ("state", value.state_buckets),
        ("decision", value.decision_buckets),
        ("workflow", value.workflow_buckets),
    ):
        for bucket in buckets:
            writer.writerow((kind, bucket.bucket_key, bucket.count, bucket.share_basis_points))
    return output.getvalue()


def mission_plan_release_catalog_report_markdown(
    report: MissionPlanReleaseCatalogReport | Mapping[str, Any],
) -> str:
    """Return a deterministic human-readable catalog report."""

    value = report if isinstance(report, MissionPlanReleaseCatalogReport) else MissionPlanReleaseCatalogReport.from_mapping(report)
    lines = [
        "# Mission plan release catalog report",
        "",
        f"- Catalog: `{value.catalog_id}`",
        f"- Catalog address: `{value.catalog_address}`",
        f"- Entries: {value.entry_count}",
        f"- Accepted entries: {value.accepted_entry_count}",
        f"- Rejected entries: {value.rejected_entry_count}",
        f"- Total steps: {value.total_step_count}",
        f"- Total artifacts: {value.total_artifact_count}",
        f"- Total checks: {value.total_check_count}",
        f"- Total warnings: {value.total_warning_count}",
        f"- Accepted: {str(value.accepted).lower()}",
        "",
    ]
    for title, buckets in (
        ("State distribution", value.state_buckets),
        ("Decision distribution", value.decision_buckets),
        ("Workflow distribution", value.workflow_buckets),
    ):
        lines.extend((f"## {title}", "", "| Key | Count | Share (basis points) |", "| --- | ---: | ---: |"))
        lines.extend(f"| {item.bucket_key} | {item.count} | {item.share_basis_points} |" for item in buckets)
        lines.append("")
    return "\n".join(lines)


def mission_plan_release_catalog_report_export_payloads(
    report: MissionPlanReleaseCatalogReport | Mapping[str, Any],
) -> dict[str, str]:
    """Return all deterministic report projections."""

    value = report if isinstance(report, MissionPlanReleaseCatalogReport) else MissionPlanReleaseCatalogReport.from_mapping(report)
    return {
        "mission-plan-release-catalog-report.json": mission_plan_release_catalog_report_json(value),
        "mission-plan-release-catalog-report.csv": mission_plan_release_catalog_report_csv(value),
        "mission-plan-release-catalog-report.md": mission_plan_release_catalog_report_markdown(value),
    }


def mission_plan_release_catalog_report_schema() -> dict[str, Any]:
    """Describe the report contract without runtime metadata."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_REPORT_SCHEMA_VERSION,
        "report_version": MISSION_PLAN_RELEASE_CATALOG_REPORT_VERSION,
        "share_unit": "basis_points",
        "share_denominator": MISSION_PLAN_RELEASE_CATALOG_REPORT_SHARE_BASIS_POINTS,
        "max_buckets": MISSION_PLAN_RELEASE_CATALOG_REPORT_MAX_BUCKETS,
        "totals": [
            "entry_count",
            "accepted_entry_count",
            "rejected_entry_count",
            "total_step_count",
            "total_optional_step_count",
            "total_deterministic_step_count",
            "total_network_step_count",
            "total_artifact_count",
            "total_check_count",
            "total_warning_count",
            "workflow_kind_count",
        ],
        "bucket_fields": ["bucket_key", "count", "share_basis_points", "content_address"],
        "boundary": {
            "request_payload": False,
            "routing_metadata": False,
            "identity_metadata": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
        },
    }


def mission_plan_release_catalog_report_capabilities() -> dict[str, Any]:
    """Describe supported report operations."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_REPORT_CAPABILITIES_VERSION,
        "aggregate_counts": True,
        "state_distribution": True,
        "decision_distribution": True,
        "workflow_distribution": True,
        "basis_point_shares": True,
        "address_reconstruction": True,
        "strict_mapping_hydration": True,
        "verified_offline_input": True,
        "read_only": True,
        "timestamp_free": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "handler_execution": False,
        "clinical_authorization": False,
        "boundary": {
            "raw_request_payload": False,
            "routing_metadata": False,
            "attribution": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
            "identity_metadata": False,
        },
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_REPORT_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_REPORT_MAX_BUCKETS",
    "MISSION_PLAN_RELEASE_CATALOG_REPORT_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_REPORT_SHARE_BASIS_POINTS",
    "MISSION_PLAN_RELEASE_CATALOG_REPORT_VERSION",
    "MissionPlanReleaseCatalogReport",
    "MissionPlanReleaseCatalogReportBucket",
    "build_mission_plan_release_catalog_report",
    "mission_plan_release_catalog_report_capabilities",
    "mission_plan_release_catalog_report_csv",
    "mission_plan_release_catalog_report_export_payloads",
    "mission_plan_release_catalog_report_json",
    "mission_plan_release_catalog_report_markdown",
    "mission_plan_release_catalog_report_schema",
]
