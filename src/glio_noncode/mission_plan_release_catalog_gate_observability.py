"""Aggregate, timestamp-free observability for catalog-gate handoffs.

This projection turns a gate and its optional deterministic runtime into
review metrics without retaining source release rows or runtime internals.
Metric values are aggregate integers, every metric is addressed, and the
projection is safe to publish beside a verified packet.  It is deliberately
descriptive: it does not execute work, infer scientific meaning, or authorize
clinical use.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog_gate import (
    MissionPlanReleaseCatalogGate,
    MissionPlanReleaseCatalogGateCheck,
)
from .mission_plan_release_catalog_gate_runtime import (
    MissionPlanReleaseCatalogGateRuntime,
    MissionPlanReleaseCatalogGateRuntimeStage,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_VERSION = "mission-plan-release-catalog-gate-observability-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_SCHEMA_VERSION = "mission-plan-release-catalog-gate-observability-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_CAPABILITIES_VERSION = "mission-plan-release-catalog-gate-observability-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_MAX_METRICS = 64

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
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


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if parsed < 0:
        raise ValidationError(f"{field} must be non-negative")
    return parsed


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
class MissionPlanReleaseCatalogGateMetric:
    """One aggregate integer metric for a catalog-gate projection."""

    metric_id: str
    category: str
    value: int
    unit: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.metric_id, "catalog_gate_metric.metric_id", maximum=128)
        _text(self.category, "catalog_gate_metric.category", maximum=64)
        _nonnegative_int(self.value, "catalog_gate_metric.value")
        _text(self.unit, "catalog_gate_metric.unit", maximum=48)
        _text(self.content_address, "catalog_gate_metric.content_address")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGateMetric":
        body = _mapping(value, "catalog gate metric")
        allowed = {"metric_id", "category", "value", "unit", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate metric contains unsupported fields: {sorted(unknown)}")
        metric = cls(
            metric_id=_text(body.get("metric_id"), "catalog_gate_metric.metric_id", maximum=128),
            category=_text(body.get("category"), "catalog_gate_metric.category", maximum=64),
            value=_nonnegative_int(body.get("value"), "catalog_gate_metric.value"),
            unit=_text(body.get("unit"), "catalog_gate_metric.unit", maximum=48),
            content_address=_text(body.get("content_address"), "catalog_gate_metric.content_address"),
        )
        expected = {key: getattr(metric, key) for key in ("metric_id", "category", "value", "unit")}
        if metric.content_address != content_hash(expected, prefix="mission-plan-release-catalog-gate-metric"):
            raise ValidationError("catalog gate metric content address does not reconcile")
        return metric

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGateObservability:
    """Addressed aggregate metrics for one gate and optional runtime."""

    observability_version: str
    catalog_id: str
    catalog_address: str
    gate_address: str
    runtime_address: str | None
    metrics: tuple[MissionPlanReleaseCatalogGateMetric, ...]
    metric_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.observability_version != MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_VERSION:
            raise ValidationError("catalog gate observability version is invalid")
        _text(self.catalog_id, "catalog_gate_observability.catalog_id", maximum=96)
        for field in ("catalog_address", "gate_address", "content_address"):
            _text(getattr(self, field), f"catalog_gate_observability.{field}")
        if self.runtime_address is not None:
            _text(self.runtime_address, "catalog_gate_observability.runtime_address")
        if len(self.metrics) > MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_MAX_METRICS:
            raise ValidationError("catalog gate observability metric count exceeds the bound")
        if self.metric_count != len(self.metrics):
            raise ValidationError("catalog gate observability metric count does not reconcile")
        identifiers = tuple(item.metric_id for item in self.metrics)
        if identifiers != tuple(sorted(identifiers)) or len(identifiers) != len(set(identifiers)):
            raise ValidationError("catalog gate observability metrics must be sorted and unique")
        _bool(self.accepted, "catalog_gate_observability.accepted")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGateObservability":
        body = _mapping(value, "mission plan release catalog gate observability")
        allowed = {
            "observability_version",
            "catalog_id",
            "catalog_address",
            "gate_address",
            "runtime_address",
            "metric_count",
            "metrics",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate observability contains unsupported fields: {sorted(unknown)}")
        raw_metrics = body.get("metrics", ())
        if not isinstance(raw_metrics, (list, tuple)):
            raise ValidationError("catalog gate observability metrics must be an array")
        observability = cls(
            observability_version=_text(body.get("observability_version"), "catalog_gate_observability.observability_version"),
            catalog_id=_text(body.get("catalog_id"), "catalog_gate_observability.catalog_id", maximum=96),
            catalog_address=_text(body.get("catalog_address"), "catalog_gate_observability.catalog_address"),
            gate_address=_text(body.get("gate_address"), "catalog_gate_observability.gate_address"),
            runtime_address=None if body.get("runtime_address") is None else _text(body.get("runtime_address"), "catalog_gate_observability.runtime_address"),
            metrics=tuple(MissionPlanReleaseCatalogGateMetric.from_mapping(item) for item in raw_metrics),
            metric_count=_nonnegative_int(body.get("metric_count"), "catalog_gate_observability.metric_count"),
            accepted=_bool(body.get("accepted"), "catalog_gate_observability.accepted"),
            content_address=_text(body.get("content_address"), "catalog_gate_observability.content_address"),
        )
        expected = _observability_address_body(observability)
        if observability.content_address != content_hash(expected, prefix="mission-plan-release-catalog-gate-observability"):
            raise ValidationError("catalog gate observability content address does not reconcile")
        if _private_paths(observability.to_dict()):
            raise ValidationError("catalog gate observability contains restricted metadata")
        return observability

    def to_dict(self) -> dict[str, Any]:
        body = {
            "observability_version": self.observability_version,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "gate_address": self.gate_address,
            "runtime_address": self.runtime_address,
            "metric_count": len(self.metrics),
            "metrics": self.metrics,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _observability_address_body(value: MissionPlanReleaseCatalogGateObservability) -> dict[str, Any]:
    return {
        "observability_version": value.observability_version,
        "catalog_id": value.catalog_id,
        "catalog_address": value.catalog_address,
        "gate_address": value.gate_address,
        "runtime_address": value.runtime_address,
        "metrics": value.metrics,
        "accepted": value.accepted,
    }


def _as_gate(value: MissionPlanReleaseCatalogGate | Mapping[str, Any]) -> MissionPlanReleaseCatalogGate:
    if isinstance(value, MissionPlanReleaseCatalogGate):
        return value
    return MissionPlanReleaseCatalogGate.from_mapping(_mapping(value, "catalog gate observability gate"))


def _as_runtime(value: MissionPlanReleaseCatalogGateRuntime | Mapping[str, Any] | None) -> MissionPlanReleaseCatalogGateRuntime | None:
    if value is None:
        return None
    if isinstance(value, MissionPlanReleaseCatalogGateRuntime):
        return value
    return MissionPlanReleaseCatalogGateRuntime.from_mapping(_mapping(value, "catalog gate observability runtime"))


def _metric(metric_id: str, category: str, value: int, unit: str) -> MissionPlanReleaseCatalogGateMetric:
    body = {"metric_id": metric_id, "category": category, "value": value, "unit": unit}
    return MissionPlanReleaseCatalogGateMetric(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-gate-metric"),
    )


def _check_metrics(checks: tuple[MissionPlanReleaseCatalogGateCheck, ...]) -> list[MissionPlanReleaseCatalogGateMetric]:
    categories = Counter(item.category for item in checks)
    accepted_categories = Counter(item.category for item in checks if item.accepted)
    metrics: list[MissionPlanReleaseCatalogGateMetric] = []
    for category in sorted(categories):
        metrics.extend(
            (
                _metric(f"checks.{category}.total", "checks", categories[category], "checks"),
                _metric(f"checks.{category}.accepted", "checks", accepted_categories[category], "checks"),
                _metric(f"checks.{category}.failed", "checks", categories[category] - accepted_categories[category], "checks"),
            )
        )
    return metrics


def _stage_metrics(stages: tuple[MissionPlanReleaseCatalogGateRuntimeStage, ...]) -> list[MissionPlanReleaseCatalogGateMetric]:
    states = Counter(item.state.value for item in stages)
    return [
        _metric(f"runtime.stages.{state}", "runtime", states[state], "stages")
        for state in ("completed", "failed", "skipped")
    ]


def build_mission_plan_release_catalog_gate_observability(
    value: MissionPlanReleaseCatalogGate | Mapping[str, Any],
    runtime: MissionPlanReleaseCatalogGateRuntime | Mapping[str, Any] | None = None,
) -> MissionPlanReleaseCatalogGateObservability:
    """Build deterministic aggregate metrics from a gate and optional runtime."""

    gate = _as_gate(value)
    selected_runtime = _as_runtime(runtime)
    if selected_runtime is not None:
        if selected_runtime.catalog_id != gate.catalog_id or selected_runtime.gate_address != gate.content_address:
            raise ValidationError("catalog gate observability runtime does not describe the gate")
    metrics = [
        _metric("gate.checks.total", "gate", len(gate.checks), "checks"),
        _metric("gate.checks.accepted", "gate", gate.passed_check_count, "checks"),
        _metric("gate.checks.failed", "gate", gate.failed_check_count, "checks"),
        _metric("gate.accepted", "gate", int(gate.accepted), "boolean"),
        _metric("gate.policy.minimum_entry_count", "policy", gate.policy.minimum_entry_count, "entries"),
        _metric("gate.policy.maximum_entry_count", "policy", gate.policy.maximum_entry_count, "entries"),
    ]
    metrics.extend(_check_metrics(gate.checks))
    if selected_runtime is not None:
        metrics.extend(_stage_metrics(selected_runtime.stages))
        metrics.extend(
            (
                _metric("runtime.stages.total", "runtime", len(selected_runtime.stages), "stages"),
                _metric("runtime.accepted", "runtime", int(selected_runtime.accepted), "boolean"),
                _metric("runtime.replay.deterministic", "runtime", int(selected_runtime.replay_deterministic), "boolean"),
            )
        )
    metrics = sorted(metrics, key=lambda item: item.metric_id)
    if len(metrics) > MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_MAX_METRICS:
        raise ValidationError("catalog gate observability metric count exceeds the bound")
    body = {
        "observability_version": MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_VERSION,
        "catalog_id": gate.catalog_id,
        "catalog_address": gate.catalog_address,
        "gate_address": gate.content_address,
        "runtime_address": None if selected_runtime is None else selected_runtime.content_address,
        "metrics": tuple(metrics),
        "accepted": gate.accepted and (selected_runtime is None or selected_runtime.accepted),
    }
    return MissionPlanReleaseCatalogGateObservability(
        **body,
        metric_count=len(metrics),
        content_address=content_hash(body, prefix="mission-plan-release-catalog-gate-observability"),
    )


def mission_plan_release_catalog_gate_observability_json(value: MissionPlanReleaseCatalogGateObservability | Mapping[str, Any]) -> str:
    observability = value if isinstance(value, MissionPlanReleaseCatalogGateObservability) else MissionPlanReleaseCatalogGateObservability.from_mapping(value)
    return canonical_json(observability.to_dict())


def mission_plan_release_catalog_gate_observability_csv(value: MissionPlanReleaseCatalogGateObservability | Mapping[str, Any]) -> str:
    observability = value if isinstance(value, MissionPlanReleaseCatalogGateObservability) else MissionPlanReleaseCatalogGateObservability.from_mapping(value)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("metric_id", "category", "value", "unit", "content_address"))
    for metric in observability.metrics:
        writer.writerow((metric.metric_id, metric.category, metric.value, metric.unit, metric.content_address))
    return output.getvalue()


def mission_plan_release_catalog_gate_observability_markdown(value: MissionPlanReleaseCatalogGateObservability | Mapping[str, Any]) -> str:
    observability = value if isinstance(value, MissionPlanReleaseCatalogGateObservability) else MissionPlanReleaseCatalogGateObservability.from_mapping(value)
    lines = [
        "# Mission plan release catalog gate observability",
        "",
        f"- Catalog: `{observability.catalog_id}`",
        f"- Catalog address: `{observability.catalog_address}`",
        f"- Gate address: `{observability.gate_address}`",
        f"- Runtime address: `{observability.runtime_address or 'not-provided'}`",
        f"- Metrics: {observability.metric_count}",
        f"- Accepted: {str(observability.accepted).lower()}",
        "",
        "| Metric | Category | Value | Unit |",
        "| --- | --- | ---: | --- |",
    ]
    lines.extend(f"| `{metric.metric_id}` | `{metric.category}` | {metric.value} | {metric.unit} |" for metric in observability.metrics)
    return "\n".join(lines) + "\n"


def mission_plan_release_catalog_gate_observability_export_payloads(value: MissionPlanReleaseCatalogGateObservability | Mapping[str, Any]) -> dict[str, str]:
    observability = value if isinstance(value, MissionPlanReleaseCatalogGateObservability) else MissionPlanReleaseCatalogGateObservability.from_mapping(value)
    return {
        "mission-plan-release-catalog-gate-observability.json": mission_plan_release_catalog_gate_observability_json(observability),
        "mission-plan-release-catalog-gate-observability.csv": mission_plan_release_catalog_gate_observability_csv(observability),
        "mission-plan-release-catalog-gate-observability.md": mission_plan_release_catalog_gate_observability_markdown(observability),
    }


def mission_plan_release_catalog_gate_observability_schema() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_SCHEMA_VERSION,
        "observability_version": MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_VERSION,
        "max_metrics": MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_MAX_METRICS,
        "metric_fields": ["metric_id", "category", "value", "unit", "content_address"],
        "categories": ["gate", "checks", "policy", "runtime"],
        "timestamp_free": True,
        "aggregate_only": True,
        "handler_execution": False,
    }


def mission_plan_release_catalog_gate_observability_capabilities() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_CAPABILITIES_VERSION,
        "aggregate_gate_metrics": True,
        "aggregate_runtime_metrics": True,
        "category_metrics": True,
        "address_reconstruction": True,
        "strict_mapping_hydration": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "read_only": True,
        "aggregate_only": True,
        "timestamp_free": True,
        "handler_execution": False,
        "clinical_authorization": False,
        "boundary": {
            "raw_request_payload": False,
            "routing_metadata": False,
            "identity_metadata": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
        },
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_MAX_METRICS",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_OBSERVABILITY_VERSION",
    "MissionPlanReleaseCatalogGateMetric",
    "MissionPlanReleaseCatalogGateObservability",
    "build_mission_plan_release_catalog_gate_observability",
    "mission_plan_release_catalog_gate_observability_capabilities",
    "mission_plan_release_catalog_gate_observability_csv",
    "mission_plan_release_catalog_gate_observability_export_payloads",
    "mission_plan_release_catalog_gate_observability_json",
    "mission_plan_release_catalog_gate_observability_markdown",
    "mission_plan_release_catalog_gate_observability_schema",
]
