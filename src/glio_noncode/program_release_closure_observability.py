"""Deterministic event and metric projection for closure operations."""

from __future__ import annotations

from .program_release_closure_contracts import (
    PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_EVENT_COUNT,
    PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_METRIC_COUNT,
    ProgramReleaseEvent,
    ProgramReleaseMetric,
    ProgramReleaseObservability,
    ProgramReleaseSnapshot,
)
from .serialization import content_hash


def _event(
    sequence: int, event_type: str, domain_id: str, input_address: str, output_address: str
) -> ProgramReleaseEvent:
    body = {
        "sequence": sequence,
        "event_id": f"event:{sequence:04d}:{event_type}",
        "event_type": event_type,
        "domain_id": domain_id,
        "input_address": input_address,
        "output_address": output_address,
    }
    return ProgramReleaseEvent(
        **body, content_address=content_hash(body, prefix="program-release-event")
    )


def _metric(domain_id: str, name: str, value: int | float, unit: str) -> ProgramReleaseMetric:
    body = {
        "metric_id": f"metric:{domain_id}:{name}",
        "domain_id": domain_id,
        "name": name,
        "value": value,
        "unit": unit,
    }
    return ProgramReleaseMetric(
        **body, content_address=content_hash(body, prefix="program-release-metric")
    )


def build_program_release_observability(
    snapshot: ProgramReleaseSnapshot,
) -> ProgramReleaseObservability:
    events: list[ProgramReleaseEvent] = []
    sequence = 1
    for domain in snapshot.domains:
        events.append(
            _event(
                sequence,
                "domain_started",
                domain.domain_id,
                snapshot.source_bundle_address,
                domain.content_address,
            )
        )
        sequence += 1
    for artifact in snapshot.artifacts:
        events.append(
            _event(
                sequence,
                "artifact_indexed",
                "__program__",
                artifact.source_address,
                artifact.content_address,
            )
        )
        sequence += 1
    for dependency in snapshot.dependencies:
        events.append(
            _event(
                sequence,
                "dependency_ordered",
                dependency.source_domain_id,
                dependency.content_address,
                f"domain:{dependency.target_domain_id}",
            )
        )
        sequence += 1
    for gate in snapshot.gates:
        events.append(
            _event(
                sequence,
                "gate_evaluated",
                gate.domain_id,
                gate.source_address,
                gate.content_address,
            )
        )
        sequence += 1
    for domain in snapshot.domains:
        events.append(
            _event(
                sequence,
                "domain_finalized",
                domain.domain_id,
                domain.content_address,
                snapshot.content_address,
            )
        )
        sequence += 1
    metrics = tuple(
        metric
        for domain in snapshot.domains
        for metric in (
            _metric(domain.domain_id, "runtime_stage_count", domain.stage_count, "stages"),
            _metric(
                domain.domain_id, "evaluation_check_count", domain.evaluation_check_count, "checks"
            ),
            _metric(
                domain.domain_id, "source_artifact_count", domain.source_artifact_count, "artifacts"
            ),
            _metric(domain.domain_id, "accepted", int(domain.accepted), "boolean"),
            _metric(
                domain.domain_id,
                "gate_count",
                sum(item.domain_id == domain.domain_id for item in snapshot.gates),
                "gates",
            ),
            _metric(
                domain.domain_id,
                "runtime_address_present",
                int(bool(domain.source_runtime_address)),
                "boolean",
            ),
        )
    )
    accepted = (
        len(events) == PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_EVENT_COUNT
        and len(metrics) == PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_METRIC_COUNT
        and all(domain_id for domain_id in (item.domain_id for item in events))
    )
    body = {
        "bundle_id": snapshot.bundle_id,
        "events": tuple(events),
        "metrics": metrics,
        "accepted": accepted,
    }
    return ProgramReleaseObservability(
        snapshot.bundle_id,
        tuple(events),
        metrics,
        accepted,
        content_hash(body, prefix="program-release-observability"),
    )


def audit_program_release_observability(
    observability: ProgramReleaseObservability,
) -> dict[str, object]:
    checks = {
        "event_count": len(observability.events)
        == PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_EVENT_COUNT,
        "metric_count": len(observability.metrics)
        == PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_METRIC_COUNT,
        "event_sequence": tuple(item.sequence for item in observability.events)
        == tuple(range(1, len(observability.events) + 1)),
        "event_id_unique": len({item.event_id for item in observability.events})
        == len(observability.events),
        "metric_id_unique": len({item.metric_id for item in observability.metrics})
        == len(observability.metrics),
        "accepted": observability.accepted,
    }
    body = {
        "bundle_id": observability.bundle_id,
        "checks": checks,
        "accepted": all(checks.values()),
    }
    body["content_address"] = content_hash(body, prefix="program-release-observability-audit")
    return body


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE")
    or name.startswith("build_program_release")
    or name.startswith("audit_program_release")
    or name.startswith("ProgramRelease")
]
