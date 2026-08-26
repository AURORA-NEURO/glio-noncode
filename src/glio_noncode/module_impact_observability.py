"""Deterministic metrics and events for module impact review."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_impact_contracts import (
    ImpactResource,
    ModuleImpactDiff,
    ModuleImpactEvent,
    ModuleImpactGate,
    ModuleImpactMetric,
    ModuleImpactObservability,
    ModuleImpactReport,
    ModuleImpactVerificationPlan,
)
from .serialization import content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _metric(metric_id: str, category: str, value: float, unit: str) -> ModuleImpactMetric:
    body = {"metric_id": metric_id, "category": category, "value": value, "unit": unit}
    return ModuleImpactMetric(**body, content_address=_address(body, "module-impact-metric"))


def _event(
    sequence: int,
    event_type: str,
    module_id: str,
    state: str,
    value: int,
    detail: str,
) -> ModuleImpactEvent:
    body = {
        "sequence": sequence,
        "event_type": event_type,
        "module_id": module_id,
        "state": state,
        "value": value,
        "detail": detail,
    }
    return ModuleImpactEvent(**body, content_address=_address(body, "module-impact-event"))


def build_module_impact_observability(
    diff: ModuleImpactDiff,
    report: ModuleImpactReport,
    plan: ModuleImpactVerificationPlan,
    gate: ModuleImpactGate,
) -> ModuleImpactObservability:
    """Aggregate the impact closure without emitting source payloads or timestamps."""

    if not all(
        isinstance(
            item,
            (ModuleImpactDiff, ModuleImpactReport, ModuleImpactVerificationPlan, ModuleImpactGate),
        )
        for item in (diff, report, plan, gate)
    ):
        raise ValidationError("impact observability requires typed closure objects")
    metrics = (
        _metric("changes", "diff", diff.change_count, "rows"),
        _metric("added", "diff", diff.added_count, "modules"),
        _metric("removed", "diff", diff.removed_count, "modules"),
        _metric("changed", "diff", diff.changed_count, "modules"),
        _metric("dependency_changes", "diff", diff.dependency_change_count, "edges"),
        _metric("impacts", "impact", report.impact_count, "modules"),
        _metric("critical_impacts", "impact", report.critical_count, "modules"),
        _metric("high_impacts", "impact", report.high_count, "modules"),
        _metric("verification_tasks", "verification", plan.task_count, "tasks"),
        _metric("gate_checks", "policy", len(gate.checks), "checks"),
        _metric("gate_passed", "policy", gate.passed_count, "checks"),
        _metric("accepted", "policy", int(gate.accepted), "boolean"),
    )
    events = (
        _event(
            1,
            "diff",
            "__aggregate__",
            "accepted" if diff.accepted else "blocked",
            diff.change_count,
            "module row diff closed",
        ),
        _event(
            2,
            "dependency",
            "__aggregate__",
            "accepted",
            diff.dependency_change_count,
            "dependency edge diff closed",
        ),
        _event(
            3,
            "impact",
            "__aggregate__",
            "accepted" if report.accepted else "blocked",
            report.impact_count,
            "reverse dependency closure closed",
        ),
        _event(
            4,
            "verification",
            "__aggregate__",
            "accepted" if plan.accepted else "blocked",
            plan.task_count,
            "verification task plan closed",
        ),
        _event(
            5,
            "policy",
            "__aggregate__",
            "accepted" if gate.accepted else "blocked",
            gate.passed_count,
            "policy checks passed",
        ),
    )
    body = {
        "diff_address": diff.content_address,
        "events": events,
        "metrics": metrics,
        "accepted": diff.accepted and report.accepted and plan.accepted and gate.accepted,
    }
    return ModuleImpactObservability(
        **body, content_address=_address(body, "module-impact-observability")
    )


def query_module_impact_observability(
    value: ModuleImpactObservability,
    *,
    resource: str = "metrics",
    event_type: str | None = None,
    state: str | None = None,
    category: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a bounded page over timestamp-free event or metric rows."""

    if not isinstance(value, ModuleImpactObservability):
        raise ValidationError("impact observability query requires a typed object")
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("invalid impact observability pagination")
    try:
        selected = ImpactResource(str(resource).casefold())
    except ValueError as exc:
        raise ValidationError(f"unsupported impact observability resource: {resource}") from exc
    if selected is ImpactResource.EVENTS:
        rows: list[Any] = list(value.events)
        if event_type is not None:
            rows = [item for item in rows if item.event_type == event_type]
        if state is not None:
            rows = [item for item in rows if item.state == state]
    elif selected is ImpactResource.METRICS:
        rows = list(value.metrics)
        if category is not None:
            rows = [item for item in rows if item.category == category]
    else:
        raise ValidationError("impact observability resource must be events or metrics")
    page = tuple(rows[offset : offset + limit])
    body = {
        "resource": selected,
        "query": {
            "event_type": event_type,
            "state": state,
            "category": category,
            "offset": offset,
            "limit": limit,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": page,
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-impact-observability-query")}


def module_impact_observability_json(value: ModuleImpactObservability) -> str:
    from .serialization import canonical_json

    return canonical_json(value.to_dict()) + "\n"


def _rows_csv(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    return output.getvalue()


def module_impact_events_csv(value: ModuleImpactObservability) -> str:
    return _rows_csv(
        [item.to_dict() for item in value.events],
        ("sequence", "event_type", "module_id", "state", "value", "detail", "content_address"),
    )


def module_impact_metrics_csv(value: ModuleImpactObservability) -> str:
    return _rows_csv(
        [item.to_dict() for item in value.metrics],
        ("metric_id", "category", "value", "unit", "content_address"),
    )


def module_impact_observability_schema() -> dict[str, Any]:
    return {
        "version": "module-impact-observability-v1",
        "boundary": "public_aggregate_module_impact_observability",
        "event_fields": [
            "sequence",
            "event_type",
            "module_id",
            "state",
            "value",
            "detail",
            "content_address",
        ],
        "metric_fields": ["metric_id", "category", "value", "unit", "content_address"],
        "resources": ["events", "metrics"],
        "timestamp_free": True,
        "maximum_events": 256,
    }


def module_impact_observability_capabilities() -> dict[str, Any]:
    operations = (
        "record_diff_event",
        "record_dependency_event",
        "record_impact_event",
        "record_verification_event",
        "record_policy_event",
        "aggregate_change_metrics",
        "aggregate_impact_metrics",
        "aggregate_policy_metrics",
        "query_events",
        "query_metrics",
        "export_csv",
    )
    return {
        "version": "module-impact-observability-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "timestamp_free": True,
        "read_only": True,
    }


__all__ = [
    "build_module_impact_observability",
    "module_impact_observability_capabilities",
    "module_impact_events_csv",
    "module_impact_observability_json",
    "module_impact_observability_schema",
    "module_impact_metrics_csv",
    "query_module_impact_observability",
]
