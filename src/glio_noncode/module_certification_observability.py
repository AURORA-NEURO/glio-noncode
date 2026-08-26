"""Deterministic metrics, events, and bounded queries for certification."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import (
    MODULE_CERTIFICATION_MAX_EVENTS,
    MODULE_CERTIFICATION_MAX_LIMIT,
    MODULE_CERTIFICATION_VERSION,
    CertificationResource,
    ModuleCertificationEvent,
    ModuleCertificationGate,
    ModuleCertificationMatrix,
    ModuleCertificationMetric,
    ModuleCertificationObservability,
    ModuleCertificationRuntime,
    ModuleCertificationTaskPlan,
)
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _metric(metric_id: str, category: str, value: float, unit: str) -> ModuleCertificationMetric:
    body = {"metric_id": metric_id, "category": category, "value": value, "unit": unit}
    return ModuleCertificationMetric(
        **body, content_address=_address(body, "module-certification-metric")
    )


def _event(
    sequence: int,
    event_type: str,
    module_id: str,
    state: str,
    value: int,
    detail: str,
) -> ModuleCertificationEvent:
    body = {
        "sequence": sequence,
        "event_type": event_type,
        "module_id": module_id,
        "state": state,
        "value": value,
        "detail": detail,
    }
    return ModuleCertificationEvent(
        **body, content_address=_address(body, "module-certification-event")
    )


def build_module_certification_observability(
    matrix: ModuleCertificationMatrix,
    plan: ModuleCertificationTaskPlan,
    gate: ModuleCertificationGate,
    runtime: ModuleCertificationRuntime,
) -> ModuleCertificationObservability:
    """Aggregate the certification closure without timestamps or source payloads."""

    typed = (matrix, plan, gate, runtime)
    if not all(
        isinstance(
            item,
            (
                ModuleCertificationMatrix,
                ModuleCertificationTaskPlan,
                ModuleCertificationGate,
                ModuleCertificationRuntime,
            ),
        )
        for item in typed
    ):
        raise ValidationError("certification observability requires typed closure objects")
    if gate.matrix_address != matrix.content_address or gate.plan_address != plan.content_address:
        raise ValidationError("certification observability has mismatched closure addresses")
    if (
        runtime.matrix_address != matrix.content_address
        or runtime.gate_address != gate.content_address
    ):
        raise ValidationError("certification observability has mismatched runtime addresses")
    metrics = (
        _metric("modules", "matrix", matrix.module_count, "modules"),
        _metric("checks", "matrix", matrix.module_count * matrix.check_kind_count, "checks"),
        _metric("passed_checks", "matrix", sum(row.passed_count for row in matrix.rows), "checks"),
        _metric("failed_checks", "matrix", sum(row.failed_count for row in matrix.rows), "checks"),
        _metric(
            "not_applicable_checks",
            "matrix",
            sum(row.not_applicable_count for row in matrix.rows),
            "checks",
        ),
        _metric("certified_modules", "matrix", matrix.certified_count, "modules"),
        _metric("review_modules", "matrix", matrix.review_count, "modules"),
        _metric("blocked_modules", "matrix", matrix.blocked_count, "modules"),
        _metric("uncovered_modules", "matrix", matrix.uncovered_count, "modules"),
        _metric("overall_score", "matrix", matrix.overall_score, "ratio"),
        _metric("gaps", "remediation", matrix.gap_count, "gaps"),
        _metric("tasks", "remediation", plan.task_count, "tasks"),
        _metric("gate_checks", "policy", len(gate.checks), "checks"),
        _metric("gate_passed", "policy", gate.passed_count, "checks"),
        _metric("accepted", "policy", int(gate.accepted), "boolean"),
        _metric("runtime_stages", "runtime", len(runtime.stages), "stages"),
    )
    events = (
        _event(
            1,
            "inventory",
            "__aggregate__",
            "accepted",
            matrix.module_count,
            "module inventory closed",
        ),
        _event(
            2,
            "checks",
            "__aggregate__",
            "accepted",
            sum(row.passed_count for row in matrix.rows),
            "module checks evaluated",
        ),
        _event(
            3,
            "gaps",
            "__aggregate__",
            "accepted" if matrix.gap_count == 0 else "review",
            matrix.gap_count,
            "certification gaps queued",
        ),
        _event(
            4,
            "tasks",
            "__aggregate__",
            "accepted" if plan.accepted else "blocked",
            plan.task_count,
            "remediation tasks derived",
        ),
        _event(
            5,
            "policy",
            "__aggregate__",
            "accepted" if gate.accepted else "blocked",
            gate.passed_count,
            "aggregate policy checks passed",
        ),
        _event(
            6,
            "runtime",
            "__aggregate__",
            "accepted" if runtime.accepted else "blocked",
            len(runtime.stages),
            "runtime stages recorded",
        ),
    )
    if len(events) > MODULE_CERTIFICATION_MAX_EVENTS:
        raise ValidationError("certification observability event limit exceeded")
    body = {
        "matrix_address": matrix.content_address,
        "events": events,
        "metrics": metrics,
        "accepted": matrix.accepted and plan.accepted and gate.accepted and runtime.accepted,
    }
    return ModuleCertificationObservability(
        **body, content_address=_address(body, "module-certification-observability")
    )


def query_module_certification_observability(
    value: ModuleCertificationObservability,
    *,
    resource: str = "metrics",
    event_type: str | None = None,
    state: str | None = None,
    category: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a bounded page over event or metric telemetry."""

    if not isinstance(value, ModuleCertificationObservability):
        raise ValidationError("certification observability query requires a typed object")
    if offset < 0 or limit < 1 or limit > MODULE_CERTIFICATION_MAX_LIMIT:
        raise ValidationError("certification observability pagination is invalid")
    try:
        selected = CertificationResource(str(resource).casefold())
    except ValueError as exc:
        raise ValidationError(
            f"unsupported certification observability resource: {resource}"
        ) from exc
    if selected is CertificationResource.EVENTS:
        rows: list[Any] = list(value.events)
        if event_type is not None:
            rows = [item for item in rows if item.event_type == event_type]
        if state is not None:
            rows = [item for item in rows if item.state == state]
    elif selected is CertificationResource.METRICS:
        rows = list(value.metrics)
        if category is not None:
            rows = [item for item in rows if item.category == category]
    else:
        raise ValidationError("certification observability resource must be events or metrics")
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
        "matrix_address": value.matrix_address,
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-certification-observability-query")}


def module_certification_observability_json(value: ModuleCertificationObservability) -> str:
    return canonical_json(value.to_dict()) + "\n"


def _csv(rows: list[Mapping[str, Any]], fields: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    return output.getvalue()


def module_certification_events_csv(value: ModuleCertificationObservability) -> str:
    fields = ("sequence", "event_type", "module_id", "state", "value", "detail", "content_address")
    return _csv([item.to_dict() for item in value.events], fields)


def module_certification_metrics_csv(value: ModuleCertificationObservability) -> str:
    fields = ("metric_id", "category", "value", "unit", "content_address")
    return _csv([item.to_dict() for item in value.metrics], fields)


def module_certification_observability_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-observability-v1",
        "boundary": "public_aggregate_module_certification_observability",
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
        "maximum_events": MODULE_CERTIFICATION_MAX_EVENTS,
        "timestamp_free": True,
    }


def module_certification_observability_capabilities() -> dict[str, Any]:
    operations = (
        "record_inventory_event",
        "record_check_event",
        "record_gap_event",
        "record_task_event",
        "record_policy_event",
        "record_runtime_event",
        "aggregate_matrix_metrics",
        "aggregate_remediation_metrics",
        "aggregate_policy_metrics",
        "query_events",
        "query_metrics",
        "export_event_csv",
        "export_metric_csv",
    )
    return {
        "version": MODULE_CERTIFICATION_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
        "timestamp_free": True,
    }


__all__ = [
    "build_module_certification_observability",
    "module_certification_events_csv",
    "module_certification_metrics_csv",
    "module_certification_observability_capabilities",
    "module_certification_observability_json",
    "module_certification_observability_schema",
    "query_module_certification_observability",
]
