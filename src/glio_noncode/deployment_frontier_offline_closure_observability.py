"""Deterministic lifecycle events and metrics for D16 closure review."""

from __future__ import annotations

from typing import Any

from .deployment_frontier_offline_closure_contracts import (
    DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVENT_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
    DeploymentFrontierClosureEvent,
    DeploymentFrontierClosureMetric,
    DeploymentFrontierClosureObservability,
    DeploymentFrontierClosurePlane,
    deployment_frontier_closure_check,
)
from .deployment_frontier_offline_closure_support import all_rows, payload
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash

DEPLOYMENT_FRONTIER_CLOSURE_OBSERVABILITY_VERSION = "deployment-frontier-closure-observability-v1"


def _event(
    sequence: int,
    event_type: str,
    resource: str,
    resource_id: str,
    state: str,
    input_address: str,
    output_address: str,
    detail: str,
) -> DeploymentFrontierClosureEvent:
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
    return DeploymentFrontierClosureEvent(
        **body, content_address=content_hash(body, prefix="deployment-frontier-closure-event")
    )


def _metric(
    metric_id: str, plane: str, name: str, value: int | float, unit: str
) -> DeploymentFrontierClosureMetric:
    body = {"metric_id": metric_id, "plane": plane, "name": name, "value": value, "unit": unit}
    return DeploymentFrontierClosureMetric(
        **body, content_address=content_hash(body, prefix="deployment-frontier-closure-metric")
    )


def build_deployment_frontier_closure_observability(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierClosureObservability:
    rows = all_rows(bundle)
    events: list[DeploymentFrontierClosureEvent] = []
    sequence = 1
    for row in rows["stages"]:
        stage_id = str(row.get("stage_id"))
        address = str(row.get("content_address", ""))
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
        state = str(row.get("expected_state", "unknown"))
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
                "record_closed",
                "record",
                record_id,
                state,
                address,
                address,
                "record closure retained",
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
                "source receipt declared",
            )
        )
        sequence += 1
    issue_count = sum(bool(row.get("issue_codes")) for row in rows["executions"])
    metrics_spec = (
        ("artifact_count", "manifest", len(rows["artifacts"]), "count"),
        ("source_count", "fixture", len(rows["sources"]), "count"),
        ("record_count", "fixture", len(rows["records"]), "count"),
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
        ("view_count", "review", len(rows["views"]), "count"),
        ("queue_count", "review", len(rows["queue"]), "count"),
        ("issue_execution_count", "review", issue_count, "count"),
        ("diagnostic_count", "review", len(rows["diagnostics"]), "count"),
        ("runtime_stage_count", "runtime", len(rows["stages"]), "count"),
        ("audit_event_count", "runtime", len(rows["audit_events"]), "count"),
        ("transcript_event_count", "runtime", len(rows["transcript_events"]), "count"),
        ("trace_observation_count", "runtime", len(rows["trace_observations"]), "count"),
        ("control_count", "release", len(rows["controls"]), "count"),
        ("failure_case_count", "release", len(rows["failures"]), "count"),
        ("closure_event_count", "observability", DEPLOYMENT_FRONTIER_CLOSURE_EVENT_COUNT, "count"),
        ("source_accepted", "release", int(bundle.accepted), "boolean"),
        ("policy_rule_count", "public", len(payload(bundle, "policy").get("rules", ())), "count"),
    )
    metrics = tuple(
        _metric(f"metric-{name}", plane, name, value, unit)
        for name, plane, value, unit in metrics_spec
    )
    accepted = (
        len(events) == DEPLOYMENT_FRONTIER_CLOSURE_EVENT_COUNT
        and len(metrics) == 24
        and all(item.content_address for item in events)
        and all(item.content_address for item in metrics)
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "events": tuple(events),
        "metrics": metrics,
        "accepted": accepted,
    }
    return DeploymentFrontierClosureObservability(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-observability"),
    )


def audit_deployment_frontier_closure_observability(
    observability: DeploymentFrontierClosureObservability,
) -> tuple[Any, ...]:
    metrics = {item.name: item.value for item in observability.metrics}
    checks = (
        deployment_frontier_closure_check(
            "observability-accepted",
            DeploymentFrontierClosurePlane.OBSERVABILITY,
            observability.accepted,
            observability.accepted,
            True,
            "observability is accepted",
        ),
        deployment_frontier_closure_check(
            "observability-events",
            DeploymentFrontierClosurePlane.OBSERVABILITY,
            len(observability.events) == DEPLOYMENT_FRONTIER_CLOSURE_EVENT_COUNT,
            len(observability.events),
            DEPLOYMENT_FRONTIER_CLOSURE_EVENT_COUNT,
            "event count is conserved",
        ),
        deployment_frontier_closure_check(
            "observability-sequence",
            DeploymentFrontierClosurePlane.OBSERVABILITY,
            tuple(item.sequence for item in observability.events)
            == tuple(range(1, DEPLOYMENT_FRONTIER_CLOSURE_EVENT_COUNT + 1)),
            (observability.events[0].sequence, observability.events[-1].sequence),
            "1..151",
            "events are sequenced",
        ),
        deployment_frontier_closure_check(
            "observability-addresses",
            DeploymentFrontierClosurePlane.OBSERVABILITY,
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
        deployment_frontier_closure_check(
            "observability-metrics",
            DeploymentFrontierClosurePlane.OBSERVABILITY,
            len(observability.metrics) == 24,
            len(observability.metrics),
            24,
            "metric set is complete",
        ),
        deployment_frontier_closure_check(
            "observability-metric-addresses",
            DeploymentFrontierClosurePlane.OBSERVABILITY,
            all(item.content_address for item in observability.metrics),
            sum(bool(item.content_address) for item in observability.metrics),
            len(observability.metrics),
            "metrics are addressed",
        ),
        deployment_frontier_closure_check(
            "observability-artifacts",
            DeploymentFrontierClosurePlane.MANIFEST,
            metrics.get("artifact_count") == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            metrics.get("artifact_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "metric conserves artifacts",
        ),
        deployment_frontier_closure_check(
            "observability-records",
            DeploymentFrontierClosurePlane.FIXTURE,
            metrics.get("record_count") == DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            metrics.get("record_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            "metric conserves records",
        ),
        deployment_frontier_closure_check(
            "observability-evaluation",
            DeploymentFrontierClosurePlane.EVALUATION,
            metrics.get("evaluation_check_count")
            == DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            metrics.get("evaluation_check_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            "metric conserves evaluation",
        ),
        deployment_frontier_closure_check(
            "observability-validation",
            DeploymentFrontierClosurePlane.VALIDATION,
            metrics.get("validation_cell_count")
            == DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            metrics.get("validation_cell_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            "metric conserves validation",
        ),
        deployment_frontier_closure_check(
            "observability-evidence",
            DeploymentFrontierClosurePlane.EVIDENCE,
            metrics.get("evidence_cell_count") == DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            metrics.get("evidence_cell_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            "metric conserves evidence",
        ),
        deployment_frontier_closure_check(
            "observability-lineage",
            DeploymentFrontierClosurePlane.LINEAGE,
            metrics.get("lineage_edge_count") == DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            metrics.get("lineage_edge_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            "metric conserves lineage",
        ),
        deployment_frontier_closure_check(
            "observability-queue",
            DeploymentFrontierClosurePlane.REVIEW,
            metrics.get("queue_count") == DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            metrics.get("queue_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            "metric conserves queue",
        ),
        deployment_frontier_closure_check(
            "observability-diagnostics",
            DeploymentFrontierClosurePlane.REVIEW,
            metrics.get("diagnostic_count") == DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            metrics.get("diagnostic_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            "metric conserves diagnostics",
        ),
        deployment_frontier_closure_check(
            "observability-runtime",
            DeploymentFrontierClosurePlane.RUNTIME,
            metrics.get("runtime_stage_count") == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            metrics.get("runtime_stage_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            "metric conserves runtime",
        ),
    )
    return checks


__all__ = [
    "DEPLOYMENT_FRONTIER_CLOSURE_OBSERVABILITY_VERSION",
    "audit_deployment_frontier_closure_observability",
    "build_deployment_frontier_closure_observability",
]
