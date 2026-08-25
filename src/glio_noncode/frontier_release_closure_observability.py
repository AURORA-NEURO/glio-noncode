"""Deterministic cross-domain events and metrics for release review."""

from __future__ import annotations

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_EVENT_COUNT,
    FRONTIER_RELEASE_CLOSURE_METRIC_COUNT,
    FrontierReleaseClosureCheck,
    FrontierReleaseEvent,
    FrontierReleaseMetric,
    FrontierReleaseObservability,
    frontier_release_closure_check,
)
from .serialization import content_hash


def _event(
    sequence: int,
    event_type: str,
    resource: str,
    resource_id: str,
    state: str,
    input_address: str,
    output_address: str,
    detail: str,
) -> FrontierReleaseEvent:
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
    return FrontierReleaseEvent(
        **body,
        content_address=content_hash(body, prefix="frontier-release-event"),
    )


def _metric(
    metric_id: str, plane: str, name: str, value: int | float, unit: str
) -> FrontierReleaseMetric:
    body = {"metric_id": metric_id, "plane": plane, "name": name, "value": value, "unit": unit}
    return FrontierReleaseMetric(
        **body,
        content_address=content_hash(body, prefix="frontier-release-metric"),
    )


def build_frontier_release_observability(
    snapshot: FrontierReleaseSnapshot,
) -> FrontierReleaseObservability:
    events: list[FrontierReleaseEvent] = []
    sequence = 1
    for domain in snapshot.domains:
        events.append(
            _event(
                sequence,
                "domain_started",
                "domain",
                domain.domain_id,
                "started",
                snapshot.content_address,
                domain.content_address,
                "start cross-domain domain projection",
            )
        )
        sequence += 1
        for artifact in (item for item in snapshot.artifacts if item.domain_id == domain.domain_id):
            events.append(
                _event(
                    sequence,
                    "artifact_indexed",
                    "artifact",
                    artifact.artifact_ref,
                    "ready",
                    domain.content_address,
                    artifact.content_address,
                    "index namespaced source artifact",
                )
            )
            sequence += 1
        for gate in (item for item in snapshot.gates if item.domain_id == domain.domain_id):
            events.append(
                _event(
                    sequence,
                    "gate_evaluated",
                    "gate",
                    gate.gate_id,
                    "passed" if gate.passed else "failed",
                    domain.content_address,
                    gate.content_address,
                    gate.detail,
                )
            )
            sequence += 1
        events.append(
            _event(
                sequence,
                "domain_finalized",
                "domain",
                domain.domain_id,
                "accepted" if domain.accepted else "blocked",
                domain.content_address,
                domain.runtime_content_address,
                "finalize domain closure projection",
            )
        )
        sequence += 1
    for dependency in snapshot.dependencies:
        events.append(
            _event(
                sequence,
                "dependency_ordered",
                "dependency",
                dependency.dependency_id,
                "required" if dependency.required else "optional",
                f"domain:{dependency.source_domain_id}",
                dependency.content_address,
                "record release dependency ordering",
            )
        )
        sequence += 1
    metrics: list[FrontierReleaseMetric] = []
    for domain in snapshot.domains:
        metrics.extend(
            (
                _metric(
                    f"{domain.domain_id}:artifact-count",
                    "domain",
                    "artifact_count",
                    domain.artifact_count,
                    "rows",
                ),
                _metric(
                    f"{domain.domain_id}:source-count",
                    "domain",
                    "source_count",
                    domain.source_count,
                    "receipts",
                ),
                _metric(
                    f"{domain.domain_id}:record-count",
                    "domain",
                    "record_count",
                    domain.record_count,
                    "records",
                ),
                _metric(
                    f"{domain.domain_id}:evaluation-count",
                    "domain",
                    "evaluation_check_count",
                    domain.evaluation_check_count,
                    "checks",
                ),
                _metric(
                    f"{domain.domain_id}:certification-coverage",
                    "domain",
                    "certification_coverage_percent",
                    domain.certification_coverage_percent,
                    "percent",
                ),
                _metric(
                    f"{domain.domain_id}:closure-stages",
                    "domain",
                    "closure_stage_count",
                    domain.closure_stage_count,
                    "stages",
                ),
            )
        )
    accepted = (
        len(events) == FRONTIER_RELEASE_CLOSURE_EVENT_COUNT
        and len(metrics) == FRONTIER_RELEASE_CLOSURE_METRIC_COUNT
        and all(item.content_address for item in events)
        and all(item.content_address for item in metrics)
        and snapshot.accepted
    )
    body = {
        "bundle_id": snapshot.bundle_id,
        "events": tuple(events),
        "metrics": tuple(metrics),
        "accepted": accepted,
    }
    return FrontierReleaseObservability(
        **body,
        content_address=content_hash(body, prefix="frontier-release-observability"),
    )


def audit_frontier_release_observability(
    observability: FrontierReleaseObservability,
) -> tuple[FrontierReleaseClosureCheck, ...]:
    sequences = tuple(item.sequence for item in observability.events)
    checks = (
        frontier_release_closure_check(
            "observability-events",
            "observability",
            len(observability.events) == FRONTIER_RELEASE_CLOSURE_EVENT_COUNT,
            len(observability.events),
            FRONTIER_RELEASE_CLOSURE_EVENT_COUNT,
            "event denominator is conserved",
        ),
        frontier_release_closure_check(
            "observability-metrics",
            "observability",
            len(observability.metrics) == FRONTIER_RELEASE_CLOSURE_METRIC_COUNT,
            len(observability.metrics),
            FRONTIER_RELEASE_CLOSURE_METRIC_COUNT,
            "metric denominator is conserved",
        ),
        frontier_release_closure_check(
            "observability-sequence",
            "observability",
            sequences == tuple(range(1, len(sequences) + 1)),
            sequences[:3] + sequences[-3:],
            "contiguous",
            "event sequence is contiguous",
        ),
        frontier_release_closure_check(
            "observability-event-ids",
            "observability",
            len({item.resource_id + str(item.sequence) for item in observability.events})
            == len(observability.events),
            len({item.resource_id + str(item.sequence) for item in observability.events}),
            len(observability.events),
            "event identities are unique",
        ),
        frontier_release_closure_check(
            "observability-event-addresses",
            "observability",
            all(item.content_address for item in observability.events),
            sum(bool(item.content_address) for item in observability.events),
            len(observability.events),
            "events are addressed",
        ),
        frontier_release_closure_check(
            "observability-metric-addresses",
            "observability",
            all(item.content_address for item in observability.metrics),
            sum(bool(item.content_address) for item in observability.metrics),
            len(observability.metrics),
            "metrics are addressed",
        ),
        frontier_release_closure_check(
            "observability-inputs",
            "observability",
            all(item.input_address for item in observability.events),
            sum(bool(item.input_address) for item in observability.events),
            len(observability.events),
            "events retain input addresses",
        ),
        frontier_release_closure_check(
            "observability-outputs",
            "observability",
            all(item.output_address for item in observability.events),
            sum(bool(item.output_address) for item in observability.events),
            len(observability.events),
            "events retain output addresses",
        ),
        frontier_release_closure_check(
            "observability-accepted",
            "observability",
            observability.accepted,
            observability.accepted,
            True,
            "observability release projection is accepted",
        ),
    )
    return checks


__all__ = ["audit_frontier_release_observability", "build_frontier_release_observability"]
