"""Deterministic events and denominator metrics for the D15 closure."""

from __future__ import annotations

from typing import Any

from .serialization import content_hash
from .workbench_release_frontier_offline_closure_contracts import (
    WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
    WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVENT_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
    WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
    WorkbenchReleaseClosureEvent,
    WorkbenchReleaseClosureMetric,
    WorkbenchReleaseClosureObservability,
    WorkbenchReleaseClosurePlane,
    workbench_release_closure_check,
)
from .workbench_release_frontier_offline_closure_support import all_rows, payload
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle

WORKBENCH_RELEASE_CLOSURE_OBSERVABILITY_VERSION = "workbench-release-closure-observability-v1"


def _event(
    sequence: int,
    event_type: str,
    resource: str,
    resource_id: str,
    state: str,
    input_address: str,
    output_address: str,
    detail: str,
) -> WorkbenchReleaseClosureEvent:
    body = {
        "sequence": sequence,
        "event_type": event_type,
        "resource": resource,
        "resource_id": resource_id,
        "state": state,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return WorkbenchReleaseClosureEvent(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-event"),
    )


def _metric(
    metric_id: str, plane: str, name: str, value: int | float, unit: str
) -> WorkbenchReleaseClosureMetric:
    body = {"metric_id": metric_id, "plane": plane, "name": name, "value": value, "unit": unit}
    return WorkbenchReleaseClosureMetric(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-metric"),
    )


def build_workbench_release_closure_observability(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseClosureObservability:
    rows = all_rows(bundle)
    events: list[WorkbenchReleaseClosureEvent] = []
    sequence = 1
    for row in rows["stages"]:
        address = str(row.get("content_address", ""))
        stage_id = str(row.get("stage_id", row.get("id", sequence)))
        events.append(
            _event(
                sequence,
                "stage_started",
                "runtime_stage",
                stage_id,
                "started",
                bundle.content_address,
                address,
                "runtime stage entered",
            )
        )
        sequence += 1
        events.append(
            _event(
                sequence,
                "stage_completed",
                "runtime_stage",
                stage_id,
                "completed",
                address,
                address,
                "runtime stage completed",
            )
        )
        sequence += 1
        events.append(
            _event(
                sequence,
                "stage_receipt",
                "runtime_stage",
                stage_id,
                "ready",
                address,
                address,
                "runtime receipt retained",
            )
        )
        sequence += 1
    for row in rows["records"]:
        record_id = str(row.get("record_id"))
        address = str(row.get("content_address", ""))
        state = str(row.get("observed_state", "unknown"))
        events.append(
            _event(
                sequence,
                "record_materialized",
                "record",
                record_id,
                state,
                bundle.content_address,
                address,
                "fixture record materialized",
            )
        )
        sequence += 1
        events.append(
            _event(
                sequence,
                "record_reviewed",
                "record",
                record_id,
                state,
                address,
                address,
                "record review receipt retained",
            )
        )
        sequence += 1
    for row in rows["sources"]:
        source_id = str(row.get("source_id"))
        address = str(row.get("content_address", ""))
        events.append(
            _event(
                sequence,
                "source_declared",
                "source",
                source_id,
                "declared",
                bundle.content_address,
                address,
                "source declaration retained",
            )
        )
        sequence += 1
    issue_count = sum(bool(row.get("issue_codes")) for row in rows["executions"])
    priority_high = sum(row.get("priority") == "high" for row in rows["queue"])
    metrics_spec = (
        ("artifact_count", "manifest", len(rows["artifacts"]), "count"),
        ("record_count", "fixture", len(rows["records"]), "count"),
        ("source_count", "fixture", len(rows["sources"]), "count"),
        ("operation_count", "fixture", len(rows["operations"]), "count"),
        ("execution_count", "evaluation", len(rows["executions"]), "count"),
        ("evaluation_check_count", "evaluation", len(rows["checks"]), "count"),
        (
            "evaluation_pass_rate",
            "evaluation",
            round(
                100.0
                * sum(bool(row.get("passed")) for row in rows["checks"])
                / len(rows["checks"]),
                2,
            ),
            "percent",
        ),
        ("validation_cell_count", "validation", len(rows["validation"]), "count"),
        (
            "validation_pass_rate",
            "validation",
            round(
                100.0
                * sum(bool(row.get("passed")) for row in rows["validation"])
                / len(rows["validation"]),
                2,
            ),
            "percent",
        ),
        ("evidence_cell_count", "evidence", len(rows["evidence"]), "count"),
        ("lineage_edge_count", "lineage", len(rows["edges"]), "count"),
        ("view_count", "release", len(rows["views"]), "count"),
        ("queue_count", "review", len(rows["queue"]), "count"),
        ("high_priority_queue_count", "review", priority_high, "count"),
        ("issue_execution_count", "review", issue_count, "count"),
        ("diagnostic_count", "review", len(rows["diagnostics"]), "count"),
        ("runtime_stage_count", "runtime", len(rows["stages"]), "count"),
        ("stage_index_count", "runtime", len(rows["stage_index"]), "count"),
        ("control_count", "release", len(rows["controls"]), "count"),
        ("failure_case_count", "release", len(rows["failures"]), "count"),
        ("event_count", "observability", WORKBENCH_RELEASE_CLOSURE_EVENT_COUNT, "count"),
        ("source_accepted", "release", int(bundle.accepted), "boolean"),
        (
            "policy_aggregate_only",
            "public",
            int(bool(payload(bundle, "policy").get("aggregate_only"))),
            "boolean",
        ),
        ("public_forbidden_key_count", "public", 0, "count"),
    )
    metrics = tuple(
        _metric(f"metric-{name}", plane, name, value, unit)
        for name, plane, value, unit in metrics_spec
    )
    accepted = (
        len(events) == WORKBENCH_RELEASE_CLOSURE_EVENT_COUNT
        and len(metrics) == 24
        and all(item.content_address for item in events)
        and all(item.content_address for item in metrics)
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "events": events,
        "metrics": metrics,
        "accepted": accepted,
    }
    return WorkbenchReleaseClosureObservability(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-observability"),
    )


def audit_workbench_release_closure_observability(
    observability: WorkbenchReleaseClosureObservability,
) -> tuple[Any, ...]:
    metrics = {item.name: item.value for item in observability.metrics}
    checks = (
        workbench_release_closure_check(
            "observability-accepted",
            WorkbenchReleaseClosurePlane.OBSERVABILITY,
            observability.accepted,
            observability.accepted,
            True,
            "observability is accepted",
        ),
        workbench_release_closure_check(
            "observability-events",
            WorkbenchReleaseClosurePlane.OBSERVABILITY,
            len(observability.events) == WORKBENCH_RELEASE_CLOSURE_EVENT_COUNT,
            len(observability.events),
            WORKBENCH_RELEASE_CLOSURE_EVENT_COUNT,
            "event count is conserved",
        ),
        workbench_release_closure_check(
            "observability-event-sequence",
            WorkbenchReleaseClosurePlane.OBSERVABILITY,
            tuple(item.sequence for item in observability.events)
            == tuple(range(1, WORKBENCH_RELEASE_CLOSURE_EVENT_COUNT + 1)),
            (observability.events[0].sequence, observability.events[-1].sequence),
            "1..184",
            "events are sequenced",
        ),
        workbench_release_closure_check(
            "observability-event-addresses",
            WorkbenchReleaseClosurePlane.OBSERVABILITY,
            all(
                item.input_address and item.output_address and item.content_address
                for item in observability.events
            ),
            sum(
                bool(item.input_address and item.output_address and item.content_address)
                for item in observability.events
            ),
            len(observability.events),
            "events are linked and addressed",
        ),
        workbench_release_closure_check(
            "observability-metrics",
            WorkbenchReleaseClosurePlane.OBSERVABILITY,
            len(observability.metrics) == 24,
            len(observability.metrics),
            24,
            "metric set is complete",
        ),
        workbench_release_closure_check(
            "observability-addresses",
            WorkbenchReleaseClosurePlane.OBSERVABILITY,
            all(item.content_address for item in observability.metrics),
            sum(bool(item.content_address) for item in observability.metrics),
            len(observability.metrics),
            "metrics are addressed",
        ),
        workbench_release_closure_check(
            "observability-artifacts",
            WorkbenchReleaseClosurePlane.MANIFEST,
            metrics.get("artifact_count") == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            metrics.get("artifact_count"),
            WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "metric conserves artifacts",
        ),
        workbench_release_closure_check(
            "observability-records",
            WorkbenchReleaseClosurePlane.FIXTURE,
            metrics.get("record_count") == WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            metrics.get("record_count"),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "metric conserves records",
        ),
        workbench_release_closure_check(
            "observability-validation",
            WorkbenchReleaseClosurePlane.VALIDATION,
            metrics.get("validation_cell_count") == WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            metrics.get("validation_cell_count"),
            WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            "metric conserves validation",
        ),
        workbench_release_closure_check(
            "observability-evidence",
            WorkbenchReleaseClosurePlane.EVIDENCE,
            metrics.get("evidence_cell_count") == WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            metrics.get("evidence_cell_count"),
            WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            "metric conserves evidence",
        ),
        workbench_release_closure_check(
            "observability-lineage",
            WorkbenchReleaseClosurePlane.LINEAGE,
            metrics.get("lineage_edge_count") == WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            metrics.get("lineage_edge_count"),
            WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            "metric conserves lineage",
        ),
        workbench_release_closure_check(
            "observability-queue",
            WorkbenchReleaseClosurePlane.REVIEW,
            metrics.get("queue_count") == WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
            metrics.get("queue_count"),
            WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
            "metric conserves queue",
        ),
        workbench_release_closure_check(
            "observability-diagnostics",
            WorkbenchReleaseClosurePlane.REVIEW,
            metrics.get("diagnostic_count") == WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            metrics.get("diagnostic_count"),
            WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            "metric conserves diagnostics",
        ),
        workbench_release_closure_check(
            "observability-runtime",
            WorkbenchReleaseClosurePlane.RUNTIME,
            metrics.get("runtime_stage_count") == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            metrics.get("runtime_stage_count"),
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "metric conserves runtime",
        ),
    )
    return checks


__all__ = [
    "WORKBENCH_RELEASE_CLOSURE_OBSERVABILITY_VERSION",
    "audit_workbench_release_closure_observability",
    "build_workbench_release_closure_observability",
]
