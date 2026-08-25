"""Detailed deterministic events and metrics for the D13 closure runtime."""

from __future__ import annotations

from typing import Any

from .serialization import content_hash
from .validation_design_frontier_bundle_closure_contracts import (
    VALIDATION_DESIGN_CLOSURE_EVENT_COUNT,
    VALIDATION_DESIGN_CLOSURE_METRIC_COUNT,
    ValidationDesignClosureCheck,
    ValidationDesignClosureEvent,
    ValidationDesignClosureMetric,
    ValidationDesignClosureObservability,
    ValidationDesignClosurePlane,
    validation_design_closure_check,
)
from .validation_design_frontier_bundle_closure_support import all_rows, bundle_count_map
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle


def _event(
    sequence: int, event_type: str, stage: dict[str, Any], detail: str
) -> ValidationDesignClosureEvent:
    body = {
        "sequence": sequence,
        "event_type": event_type,
        "stage_id": stage.get("stage_id", ""),
        "state": stage.get("state", ""),
        "input_address": stage.get("input_address", ""),
        "output_address": stage.get("output_address", ""),
        "detail": detail,
    }
    return ValidationDesignClosureEvent(
        **body, content_address=content_hash(body, prefix="validation-design-closure-event")
    )


def _metric(
    metric_id: str, plane: str, name: str, value: int | float, unit: str
) -> ValidationDesignClosureMetric:
    body = {"metric_id": metric_id, "plane": plane, "name": name, "value": value, "unit": unit}
    return ValidationDesignClosureMetric(
        **body, content_address=content_hash(body, prefix="validation-design-closure-metric")
    )


def build_validation_design_closure_observability(
    bundle: ValidationDesignBundle,
) -> ValidationDesignClosureObservability:
    rows = all_rows(bundle)
    events: list[ValidationDesignClosureEvent] = []
    sequence = 1
    for stage in rows["stages"]:
        events.append(
            _event(
                sequence,
                "stage_started",
                stage,
                f"stage {stage.get('stage_id')} entered the closure trace",
            )
        )
        sequence += 1
        events.append(
            _event(
                sequence,
                "stage_completed",
                stage,
                f"stage {stage.get('stage_id')} completed with addressed output",
            )
        )
        sequence += 1
    counts = bundle_count_map(bundle)
    metrics = [
        _metric("metric-01", "manifest", "artifact_count", counts["artifacts"], "artifacts"),
        _metric(
            "metric-02", "manifest", "manifest_check_count", counts["manifest_checks"], "checks"
        ),
        _metric("metric-03", "fixture", "record_count", counts["records"], "records"),
        _metric("metric-04", "fixture", "source_count", counts["sources"], "sources"),
        _metric("metric-05", "fixture", "operation_count", counts["operations"], "operations"),
        _metric("metric-06", "evaluation", "execution_count", counts["executions"], "executions"),
        _metric("metric-07", "evaluation", "evaluation_check_count", counts["checks"], "checks"),
        _metric(
            "metric-08",
            "evaluation",
            "passed_evaluation_checks",
            sum(bool(row.get("passed")) for row in rows["checks"]),
            "checks",
        ),
        _metric("metric-09", "runtime", "runtime_stage_count", counts["stages"], "stages"),
        _metric("metric-10", "runtime", "runtime_plane_count", counts["planes"], "planes"),
        _metric(
            "metric-11",
            "runtime",
            "accepted_plane_count",
            sum(bool(row.get("accepted")) for row in rows["planes"]),
            "planes",
        ),
        _metric(
            "metric-12",
            "runtime",
            "addressed_stage_count",
            sum(str(row.get("output_address", "")).startswith("sha256:") for row in rows["stages"]),
            "stages",
        ),
        _metric("metric-13", "query", "indexable_resource_count", len(rows), "resources"),
        _metric("metric-14", "query", "issue_family_count", counts["issues"], "issue families"),
        _metric("metric-15", "query", "state_partition_count", counts["states"], "states"),
        _metric("metric-16", "release", "review_row_count", counts["reviews"], "rows"),
        _metric(
            "metric-17",
            "release",
            "ready_record_count",
            sum(row.get("observed_state") == "ready" for row in rows["records"]),
            "records",
        ),
        _metric(
            "metric-18", "release", "closure_acceptance", int(bool(bundle.accepted)), "boolean"
        ),
    ]
    accepted = (
        bundle.accepted
        and len(events) == VALIDATION_DESIGN_CLOSURE_EVENT_COUNT
        and len(metrics) == VALIDATION_DESIGN_CLOSURE_METRIC_COUNT
        and all(item.state == "completed" for item in events[1::2])
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "events": tuple(events),
        "metrics": tuple(metrics),
        "accepted": accepted,
    }
    return ValidationDesignClosureObservability(
        bundle_id=bundle.bundle_id,
        events=tuple(events),
        metrics=tuple(metrics),
        accepted=accepted,
        content_address=content_hash(body, prefix="validation-design-closure-observability"),
    )


def audit_validation_design_closure_observability(
    bundle: ValidationDesignBundle,
    observability: ValidationDesignClosureObservability | None = None,
) -> tuple[ValidationDesignClosureCheck, ...]:
    value = observability or build_validation_design_closure_observability(bundle)
    rows = all_rows(bundle)
    checks = [
        validation_design_closure_check(
            "observability-bundle-id",
            ValidationDesignClosurePlane.OBSERVABILITY,
            value.bundle_id == bundle.bundle_id,
            value.bundle_id,
            bundle.bundle_id,
            "events point to the source bundle",
        ),
        validation_design_closure_check(
            "observability-event-count",
            ValidationDesignClosurePlane.OBSERVABILITY,
            len(value.events) == 158,
            len(value.events),
            158,
            "two events are retained per source runtime stage",
        ),
        validation_design_closure_check(
            "observability-event-sequence",
            ValidationDesignClosurePlane.OBSERVABILITY,
            [item.sequence for item in value.events] == list(range(1, 159)),
            "contiguous",
            "1..158",
            "event sequences are contiguous",
        ),
        validation_design_closure_check(
            "observability-stage-coverage",
            ValidationDesignClosurePlane.OBSERVABILITY,
            len({item.stage_id for item in value.events}) == len(rows["stages"]),
            len({item.stage_id for item in value.events}),
            len(rows["stages"]),
            "every runtime stage emits events",
        ),
        validation_design_closure_check(
            "observability-starts",
            ValidationDesignClosurePlane.OBSERVABILITY,
            all(item.event_type == "stage_started" for item in value.events[0::2]),
            len(value.events[0::2]),
            len(rows["stages"]),
            "every stage has a start event",
        ),
        validation_design_closure_check(
            "observability-completions",
            ValidationDesignClosurePlane.OBSERVABILITY,
            all(item.event_type == "stage_completed" for item in value.events[1::2]),
            len(value.events[1::2]),
            len(rows["stages"]),
            "every stage has a completion event",
        ),
        validation_design_closure_check(
            "observability-addresses",
            ValidationDesignClosurePlane.OBSERVABILITY,
            all(
                item.content_address.startswith("validation-design-closure-event:")
                for item in value.events
            ),
            len(value.events),
            len(value.events),
            "events are addressed",
        ),
        validation_design_closure_check(
            "observability-metric-count",
            ValidationDesignClosurePlane.OBSERVABILITY,
            len(value.metrics) == 18,
            len(value.metrics),
            18,
            "metric inventory is closed",
        ),
        validation_design_closure_check(
            "observability-metric-addresses",
            ValidationDesignClosurePlane.OBSERVABILITY,
            all(
                item.content_address.startswith("validation-design-closure-metric:")
                for item in value.metrics
            ),
            len(value.metrics),
            len(value.metrics),
            "metrics are addressed",
        ),
        validation_design_closure_check(
            "observability-accepted",
            ValidationDesignClosurePlane.OBSERVABILITY,
            value.accepted,
            value.accepted,
            True,
            "observability is accepted",
        ),
    ]
    return tuple(checks)


def export_validation_design_closure_events_csv(
    observability: ValidationDesignClosureObservability,
) -> str:
    from .validation_design_frontier_bundle_closure_support import csv_text

    return csv_text([item.to_dict() for item in observability.events])


def export_validation_design_closure_metrics_csv(
    observability: ValidationDesignClosureObservability,
) -> str:
    from .validation_design_frontier_bundle_closure_support import csv_text

    return csv_text([item.to_dict() for item in observability.metrics])


__all__ = [
    "audit_validation_design_closure_observability",
    "build_validation_design_closure_observability",
    "export_validation_design_closure_events_csv",
    "export_validation_design_closure_metrics_csv",
]
