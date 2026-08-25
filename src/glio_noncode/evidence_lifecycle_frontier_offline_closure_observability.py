"""Deterministic event and metric projections for the D14 closure runtime."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EVIDENCE_LIFECYCLE_CLOSURE_EVENT_COUNT,
    EvidenceLifecycleClosureCheck,
    EvidenceLifecycleClosureEvent,
    EvidenceLifecycleClosureMetric,
    EvidenceLifecycleClosureObservability,
    evidence_lifecycle_closure_check,
)
from .evidence_lifecycle_frontier_offline_closure_support import all_rows
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureObservabilityAudit:
    bundle_id: str
    checks: tuple[EvidenceLifecycleClosureCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": sum(item.passed for item in self.checks),
            "failed_count": sum(not item.passed for item in self.checks),
            "failed_check_ids": list(self.failed_check_ids),
        }


def _event(
    sequence: int,
    event_type: str,
    resource: str,
    resource_id: str,
    state: str,
    input_address: str,
    output_address: str,
    detail: str,
) -> EvidenceLifecycleClosureEvent:
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
    return EvidenceLifecycleClosureEvent(
        **body, content_address=content_hash(body, prefix="evidence-lifecycle-closure-event")
    )


def _metric(
    metric_id: str, plane: str, name: str, value: int | float, unit: str
) -> EvidenceLifecycleClosureMetric:
    body = {"metric_id": metric_id, "plane": plane, "name": name, "value": value, "unit": unit}
    return EvidenceLifecycleClosureMetric(
        **body, content_address=content_hash(body, prefix="evidence-lifecycle-closure-metric")
    )


def build_evidence_lifecycle_closure_observability(
    bundle: EvidenceLifecycleOfflineBundle,
) -> EvidenceLifecycleClosureObservability:
    rows = all_rows(bundle)
    events: list[EvidenceLifecycleClosureEvent] = []
    sequence = 1
    for stage in rows["stages"]:
        stage_id = str(stage.get("stage_id"))
        state = str(stage.get("state", "unknown"))
        input_address = str(stage.get("input_address", bundle.content_address))
        output_address = str(stage.get("output_address", stage.get("content_address", "")))
        events.append(
            _event(
                sequence,
                "stage_started",
                "stage",
                stage_id,
                "running",
                input_address,
                input_address,
                f"closure stage {stage_id} started",
            )
        )
        sequence += 1
        events.append(
            _event(
                sequence,
                "stage_completed",
                "stage",
                stage_id,
                state,
                input_address,
                output_address,
                f"closure stage {stage_id} completed",
            )
        )
        sequence += 1
        events.append(
            _event(
                sequence,
                "stage_reconciled",
                "stage",
                stage_id,
                state,
                output_address,
                output_address,
                f"closure stage {stage_id} reconciled",
            )
        )
        sequence += 1
    for row in rows["records"]:
        record_id = str(row.get("record_id"))
        state = str(row.get("observed_state", "unknown"))
        address = str(row.get("content_address", ""))
        events.append(
            _event(
                sequence,
                "record_observed",
                "record",
                record_id,
                state,
                address,
                address,
                f"record {record_id} observed",
            )
        )
        sequence += 1
        events.append(
            _event(
                sequence,
                "record_reconciled",
                "record",
                record_id,
                state,
                address,
                address,
                f"record {record_id} reconciled",
            )
        )
        sequence += 1
    counts = Counter(str(row.get("disposition")) for row in rows["queue"])
    accepted = sum(bool(row.get("accepted")) for row in rows["executions"])
    metric_values = (
        ("artifact_count", "manifest", "artifacts", len(rows["artifacts"]), "count"),
        ("record_count", "fixture", "records", len(rows["records"]), "count"),
        ("source_count", "fixture", "sources", len(rows["sources"]), "count"),
        ("execution_count", "evaluation", "executions", len(rows["executions"]), "count"),
        ("evaluation_check_count", "evaluation", "evaluation checks", len(rows["checks"]), "count"),
        (
            "passed_evaluation_check_count",
            "evaluation",
            "passed evaluation checks",
            sum(bool(row.get("passed")) for row in rows["checks"]),
            "count",
        ),
        ("lineage_edge_count", "lineage", "lineage edges", len(rows["edges"]), "count"),
        ("queue_count", "queue", "queue items", len(rows["queue"]), "count"),
        (
            "queue_ready_count",
            "queue",
            "ready queue items",
            counts.get("ready_for_review", 0),
            "count",
        ),
        (
            "queue_held_count",
            "queue",
            "held queue items",
            counts.get("hold_for_repair", 0),
            "count",
        ),
        ("review_count", "review", "review rows", len(rows["reviews"]), "count"),
        ("scenario_count", "fixture", "scenarios", len(rows["scenarios"]), "count"),
        ("operation_count", "fixture", "operations", len(rows["operations"]), "count"),
        ("stage_count", "runtime", "source runtime stages", len(rows["stages"]), "count"),
        (
            "source_event_count",
            "observability",
            "source events",
            len(
                __import__("json").loads(
                    next(
                        item.payload
                        for item in bundle.artifacts
                        if item.artifact_id == "observability"
                    )
                )["events"]
            ),
            "count",
        ),
        ("closure_event_count", "observability", "closure events", len(events), "count"),
        (
            "issue_execution_count",
            "evaluation",
            "executions with issue codes",
            sum(bool(row.get("issue_codes")) for row in rows["executions"]),
            "count",
        ),
        (
            "execution_acceptance_rate",
            "evaluation",
            "execution acceptance rate",
            round(accepted / len(rows["executions"]), 6) if rows["executions"] else 0.0,
            "ratio",
        ),
    )
    metrics = tuple(_metric(*item) for item in metric_values)
    body = {
        "bundle_id": bundle.bundle_id,
        "events": events,
        "metrics": metrics,
        "accepted": len(events) == EVIDENCE_LIFECYCLE_CLOSURE_EVENT_COUNT and len(metrics) == 18,
    }
    return EvidenceLifecycleClosureObservability(
        bundle_id=bundle.bundle_id,
        events=tuple(events),
        metrics=metrics,
        accepted=body["accepted"],
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-observability"),
    )


def audit_evidence_lifecycle_closure_observability(
    observability: EvidenceLifecycleClosureObservability,
) -> EvidenceLifecycleClosureObservabilityAudit:
    events = observability.events
    stage_events = tuple(item for item in events if item.resource == "stage")
    record_events = tuple(item for item in events if item.resource == "record")
    checks = (
        evidence_lifecycle_closure_check(
            "observability-accepted",
            "observability",
            observability.accepted,
            observability.accepted,
            True,
            "closure observability is accepted",
        ),
        evidence_lifecycle_closure_check(
            "observability-event-count",
            "observability",
            len(events) == EVIDENCE_LIFECYCLE_CLOSURE_EVENT_COUNT,
            len(events),
            EVIDENCE_LIFECYCLE_CLOSURE_EVENT_COUNT,
            "closure event denominator is conserved",
        ),
        evidence_lifecycle_closure_check(
            "observability-sequence",
            "observability",
            [item.sequence for item in events] == list(range(1, len(events) + 1)),
            len(events),
            "contiguous",
            "event sequence is contiguous",
        ),
        evidence_lifecycle_closure_check(
            "observability-event-addresses",
            "observability",
            all(
                item.content_address.startswith("evidence-lifecycle-closure-event:")
                for item in events
            ),
            len(events),
            EVIDENCE_LIFECYCLE_CLOSURE_EVENT_COUNT,
            "events are addressed",
        ),
        evidence_lifecycle_closure_check(
            "observability-stage-coverage",
            "observability",
            len(stage_events) == 30 and len({item.resource_id for item in stage_events}) == 10,
            len(stage_events),
            30,
            "each source stage has three events",
        ),
        evidence_lifecycle_closure_check(
            "observability-record-coverage",
            "observability",
            len(record_events) == 32 and len({item.resource_id for item in record_events}) == 16,
            len(record_events),
            32,
            "each record has two events",
        ),
        evidence_lifecycle_closure_check(
            "observability-event-address-links",
            "observability",
            all(item.input_address and item.output_address for item in events),
            len(events),
            EVIDENCE_LIFECYCLE_CLOSURE_EVENT_COUNT,
            "events retain input and output addresses",
        ),
        evidence_lifecycle_closure_check(
            "observability-metric-count",
            "observability",
            len(observability.metrics) == 18,
            len(observability.metrics),
            18,
            "metric denominator is conserved",
        ),
        evidence_lifecycle_closure_check(
            "observability-metric-addresses",
            "observability",
            all(
                item.content_address.startswith("evidence-lifecycle-closure-metric:")
                for item in observability.metrics
            ),
            len(observability.metrics),
            18,
            "metrics are addressed",
        ),
        evidence_lifecycle_closure_check(
            "observability-acceptance-metric",
            "observability",
            any(item.metric_id == "execution_acceptance_rate" for item in observability.metrics),
            True,
            True,
            "acceptance ratio remains visible",
        ),
        evidence_lifecycle_closure_check(
            "observability-denominator-metric",
            "observability",
            any(
                item.metric_id == "record_count" and item.value == 16
                for item in observability.metrics
            ),
            16,
            16,
            "record denominator remains visible",
        ),
        evidence_lifecycle_closure_check(
            "observability-unique-event-addresses",
            "observability",
            len({item.content_address for item in events}) == len(events),
            len({item.content_address for item in events}),
            len(events),
            "event addresses are unique",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": observability.bundle_id, "checks": checks, "accepted": accepted}
    return EvidenceLifecycleClosureObservabilityAudit(
        bundle_id=observability.bundle_id,
        checks=checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-observability-audit"),
    )


__all__ = [
    "EvidenceLifecycleClosureObservabilityAudit",
    "audit_evidence_lifecycle_closure_observability",
    "build_evidence_lifecycle_closure_observability",
]
