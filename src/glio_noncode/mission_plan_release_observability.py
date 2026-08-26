"""Deterministic aggregate observability for verified mission-plan releases.

The release verifier establishes integrity; this module makes the verified
shape operationally inspectable.  It emits numeric, timestamp-free metrics for
workflow size, dependency depth, optionality, determinism, resources, checks,
artifacts, and the public boundary.  It never records raw request text or
internal routing metadata and does not interpret scientific meaning.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release import (
    MissionPlanOfflineRelease,
    MissionPlanReleaseBundle,
    build_mission_plan_release,
    load_mission_plan_release,
)
from .mission_runtime_public import MissionPlanPublicReceipt
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_OBSERVABILITY_VERSION = "mission-plan-release-observability-v1"
MISSION_PLAN_RELEASE_OBSERVABILITY_SCHEMA_VERSION = "mission-plan-release-observability-schema-v1"
MISSION_PLAN_RELEASE_OBSERVABILITY_CAPABILITIES_VERSION = "mission-plan-release-observability-capabilities-v1"
MISSION_PLAN_RELEASE_OBSERVABILITY_MAX_METRICS = 64


def _text(value: Any, field: str) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseMetric:
    """One stable aggregate measurement."""

    metric_id: str
    category: str
    value: float
    unit: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.metric_id, "metric_id")
        _text(self.category, "category")
        _text(self.unit, "unit")
        if self.value != self.value or self.value in (float("inf"), float("-inf")):
            raise ValidationError("metric value must be finite")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseObservability:
    """Addressed aggregate observability snapshot."""

    observability_version: str
    release_id: str
    plan_id: str
    plan_address: str
    metrics: tuple[MissionPlanReleaseMetric, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.observability_version != MISSION_PLAN_RELEASE_OBSERVABILITY_VERSION:
            raise ValidationError("observability version is invalid")
        _text(self.release_id, "observability.release_id")
        _text(self.plan_id, "observability.plan_id")
        _text(self.plan_address, "observability.plan_address")
        if len(self.metrics) > MISSION_PLAN_RELEASE_OBSERVABILITY_MAX_METRICS:
            raise ValidationError("observability metric count exceeds the bound")
        metric_ids = [item.metric_id for item in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValidationError("observability metric IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        body = {
            "observability_version": self.observability_version,
            "release_id": self.release_id,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "metric_count": len(self.metrics),
            "metrics": self.metrics,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _metric(metric_id: str, category: str, value: float, unit: str) -> MissionPlanReleaseMetric:
    body = {
        "metric_id": metric_id,
        "category": category,
        "value": float(value),
        "unit": unit,
    }
    return MissionPlanReleaseMetric(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-metric"),
    )


def _as_public_source(
    value: MissionPlanReleaseBundle | MissionPlanOfflineRelease | MissionPlanPublicReceipt | Mapping[str, Any] | str | Path,
) -> tuple[str, MissionPlanPublicReceipt, int, int, bool]:
    if isinstance(value, MissionPlanReleaseBundle):
        return value.release_id, value.receipt, len(value.artifacts), len(value.checks), value.accepted
    if isinstance(value, MissionPlanOfflineRelease):
        return value.release_id, value.receipt, int(value.manifest.get("artifact_count", 0)), len(value.checks), value.accepted
    if isinstance(value, MissionPlanPublicReceipt):
        bundle = build_mission_plan_release(value)
        return bundle.release_id, bundle.receipt, len(bundle.artifacts), len(bundle.checks), bundle.accepted
    if isinstance(value, (str, Path)):
        offline = load_mission_plan_release(value)
        return _as_public_source(offline)
    body = dict(value)
    if "receipt" in body and isinstance(body["receipt"], Mapping):
        receipt = MissionPlanPublicReceipt.from_mapping(body["receipt"])
        release_id = _text(body.get("release_id", "plan-" + receipt.plan_id), "release_id")
        bundle = build_mission_plan_release(receipt, release_id=release_id)
        return bundle.release_id, bundle.receipt, len(bundle.artifacts), len(bundle.checks), bundle.accepted
    receipt = MissionPlanPublicReceipt.from_mapping(body) if "content_address" in body else None
    if receipt is None:
        bundle = build_mission_plan_release(build_public_receipt(value))
        return bundle.release_id, bundle.receipt, len(bundle.artifacts), len(bundle.checks), bundle.accepted
    bundle = build_mission_plan_release(receipt)
    return bundle.release_id, bundle.receipt, len(bundle.artifacts), len(bundle.checks), bundle.accepted


def build_public_receipt(value: Mapping[str, Any]) -> MissionPlanPublicReceipt:
    """Build a receipt from a mission request without publishing its input."""

    from .mission_runtime_public import build_public_mission_plan

    return build_public_mission_plan(value)


def _dependency_depth(receipt: MissionPlanPublicReceipt) -> int:
    depths: dict[str, int] = {}
    for step in receipt.steps:
        depths[step.step_id] = 1 + max((depths[item] for item in step.depends_on), default=0)
    return max(depths.values(), default=0)


def build_mission_plan_release_observability(
    value: MissionPlanReleaseBundle | MissionPlanOfflineRelease | MissionPlanPublicReceipt | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseObservability:
    """Build deterministic aggregate metrics from a public release source."""

    release_id, receipt, artifact_count, check_count, accepted = _as_public_source(value)
    metrics = (
        _metric("workflow.step_count", "workflow", receipt.step_count, "steps"),
        _metric("workflow.optional_step_count", "workflow", sum(item.optional for item in receipt.steps), "steps"),
        _metric("workflow.deterministic_step_count", "workflow", sum(item.deterministic for item in receipt.steps), "steps"),
        _metric("workflow.nondeterministic_step_count", "workflow", sum(not item.deterministic for item in receipt.steps), "steps"),
        _metric("workflow.dependency_depth", "workflow", _dependency_depth(receipt), "levels"),
        _metric("workflow.network_step_count", "workflow", sum(bool(item.resource.get("network_egress", False)) for item in receipt.steps), "steps"),
        _metric("resources.total_cpu", "resources", receipt.total_cpu, "cpu"),
        _metric("resources.peak_memory_gb", "resources", receipt.peak_memory_gb, "gb"),
        _metric("resources.total_storage_gb", "resources", receipt.total_storage_gb, "gb"),
        _metric("resources.max_seconds", "resources", receipt.max_seconds, "seconds"),
        _metric("integrity.check_count", "integrity", check_count, "checks"),
        _metric("integrity.warning_count", "integrity", receipt.warning_count, "warnings"),
        _metric("integrity.artifact_count", "integrity", artifact_count, "artifacts"),
        _metric("integrity.boundary_accepted", "integrity", receipt.boundary_accepted, "boolean"),
        _metric("selection.role_count", "selection", receipt.selected_role_count, "roles"),
        _metric("selection.operation_count", "selection", receipt.selected_operation_count, "operations"),
    )
    body = {
        "observability_version": MISSION_PLAN_RELEASE_OBSERVABILITY_VERSION,
        "release_id": release_id,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "metrics": metrics,
        "accepted": accepted,
    }
    return MissionPlanReleaseObservability(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-observability"),
    )


def mission_plan_release_observability_json(value: MissionPlanReleaseObservability) -> str:
    """Render aggregate observability as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def mission_plan_release_observability_csv(value: MissionPlanReleaseObservability) -> str:
    """Render aggregate observability as deterministic CSV."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("metric_id", "category", "value", "unit", "content_address"))
    for metric in value.metrics:
        writer.writerow((metric.metric_id, metric.category, metric.value, metric.unit, metric.content_address))
    return output.getvalue()


def mission_plan_release_observability_markdown(value: MissionPlanReleaseObservability) -> str:
    """Render aggregate observability as a review table."""

    lines = [
        "# Mission plan release observability",
        "",
        f"- Release: `{value.release_id}`",
        f"- Metrics: `{len(value.metrics)}`",
        f"- Accepted: `{value.accepted}`",
        "",
        "| Metric | Category | Value | Unit |",
        "| --- | --- | ---: | --- |",
    ]
    lines.extend(
        f"| `{metric.metric_id}` | `{metric.category}` | `{metric.value}` | `{metric.unit}` |"
        for metric in value.metrics
    )
    return "\n".join(lines) + "\n"


def mission_plan_release_observability_export_payloads(
    value: MissionPlanReleaseObservability,
) -> dict[str, str]:
    """Return deterministic observability artifacts."""

    return {
        "mission-plan-release-observability.json": mission_plan_release_observability_json(value),
        "mission-plan-release-observability.csv": mission_plan_release_observability_csv(value),
        "mission-plan-release-observability.md": mission_plan_release_observability_markdown(value),
    }


def mission_plan_release_observability_schema() -> dict[str, Any]:
    """Return the aggregate observability contract."""

    return {
        "version": MISSION_PLAN_RELEASE_OBSERVABILITY_SCHEMA_VERSION,
        "observability_version": MISSION_PLAN_RELEASE_OBSERVABILITY_VERSION,
        "metric_fields": ["metric_id", "category", "value", "unit", "content_address"],
        "categories": ["workflow", "resources", "integrity", "selection"],
        "max_metrics": MISSION_PLAN_RELEASE_OBSERVABILITY_MAX_METRICS,
        "timestamp_free": True,
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_observability_capabilities() -> dict[str, Any]:
    """Return aggregate observability capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_OBSERVABILITY_CAPABILITIES_VERSION,
        "workflow_metrics": True,
        "dependency_depth": True,
        "resource_metrics": True,
        "integrity_metrics": True,
        "selection_metrics": True,
        "timestamp_free": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_OBSERVABILITY_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_OBSERVABILITY_MAX_METRICS",
    "MISSION_PLAN_RELEASE_OBSERVABILITY_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_OBSERVABILITY_VERSION",
    "MissionPlanReleaseMetric",
    "MissionPlanReleaseObservability",
    "build_mission_plan_release_observability",
    "mission_plan_release_observability_capabilities",
    "mission_plan_release_observability_csv",
    "mission_plan_release_observability_export_payloads",
    "mission_plan_release_observability_json",
    "mission_plan_release_observability_markdown",
    "mission_plan_release_observability_schema",
]
