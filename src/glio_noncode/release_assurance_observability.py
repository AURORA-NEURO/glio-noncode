"""Deterministic event and metric traces for whole-product assurance."""

from __future__ import annotations

from .release_assurance_contracts import (
    RELEASE_ASSURANCE_EVENT_COUNT,
    RELEASE_ASSURANCE_METRIC_COUNT,
    ReleaseAssuranceEvent,
    ReleaseAssuranceMetric,
    ReleaseAssuranceObservability,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    check,
)
from .serialization import content_hash

_EVENT_TYPES = (
    "source-read",
    "capability-checked",
    "architecture-checked",
    "service-checked",
    "public-boundary-checked",
    "evidence-linked",
    "checks-reconciled",
    "summary-built",
    "plan-built",
    "views-built",
    "replay-queued",
    "release-ready",
)
_METRIC_SPECS = (
    ("denominator", "rows"),
    ("accepted_count", "rows"),
    ("readiness_percent", "percent"),
    ("evidence_count", "links"),
)


def build_release_assurance_observability(
    snapshot: ReleaseAssuranceSnapshot,
) -> ReleaseAssuranceObservability:
    """Build a 12-event trace and four metrics per assurance domain."""

    events: list[ReleaseAssuranceEvent] = []
    sequence = 0
    for domain in snapshot.domains:
        previous = domain.source_address
        for event_type in _EVENT_TYPES:
            sequence += 1
            output = content_hash(
                {"domain_id": domain.domain_id, "event_type": event_type,
                 "sequence": sequence, "input_address": previous},
                prefix="release-assurance-event-output",
            )
            body = {
                "sequence": sequence,
                "event_id": f"event:{sequence:03d}:{domain.domain_id}:{event_type}",
                "event_type": event_type,
                "domain_id": domain.domain_id,
                "input_address": previous,
                "output_address": output,
            }
            events.append(ReleaseAssuranceEvent(
                **body,
                content_address=content_hash(body, prefix="release-assurance-event"),
            ))
            previous = output
    metrics: list[ReleaseAssuranceMetric] = []
    values_by_name = {
        "denominator": lambda item: item.denominator,
        "accepted_count": lambda item: item.accepted_count,
        "readiness_percent": lambda item: item.readiness_percent,
        "evidence_count": lambda item: item.evidence_count,
    }
    for domain in snapshot.domains:
        for name, unit in _METRIC_SPECS:
            body = {
                "metric_id": f"metric:{domain.domain_id}:{name}",
                "domain_id": domain.domain_id,
                "name": name,
                "value": values_by_name[name](domain),
                "unit": unit,
            }
            metrics.append(ReleaseAssuranceMetric(
                **body,
                content_address=content_hash(body, prefix="release-assurance-metric"),
            ))
    accepted = (
        snapshot.accepted
        and len(events) == RELEASE_ASSURANCE_EVENT_COUNT
        and len(metrics) == RELEASE_ASSURANCE_METRIC_COUNT
        and tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1))
    )
    body = {"bundle_id": snapshot.bundle_id, "events": events,
            "metrics": metrics, "accepted": accepted}
    return ReleaseAssuranceObservability(
        snapshot.bundle_id,
        tuple(events),
        tuple(metrics),
        accepted,
        content_hash(body, prefix="release-assurance-observability"),
    )


def audit_release_assurance_observability(
    observability: ReleaseAssuranceObservability,
) -> tuple:
    """Audit trace cardinality, ordering, and identity uniqueness."""

    events = observability.events
    return (
        check("observability:event-count", "observability", ReleaseAssurancePlane.RUNTIME,
              len(events) == RELEASE_ASSURANCE_EVENT_COUNT, len(events),
              RELEASE_ASSURANCE_EVENT_COUNT, "event denominator is conserved"),
        check("observability:metric-count", "observability", ReleaseAssurancePlane.RUNTIME,
              len(observability.metrics) == RELEASE_ASSURANCE_METRIC_COUNT,
              len(observability.metrics), RELEASE_ASSURANCE_METRIC_COUNT,
              "metric denominator is conserved"),
        check("observability:sequence", "observability", ReleaseAssurancePlane.RUNTIME,
              tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1)),
              tuple(item.sequence for item in events[:3]), "contiguous one-based sequence",
              "event order is deterministic"),
        check("observability:event-identities", "observability", ReleaseAssurancePlane.RUNTIME,
              len({item.event_id for item in events}) == len(events),
              len({item.event_id for item in events}), len(events),
              "event identities are unique"),
        check("observability:metric-identities", "observability", ReleaseAssurancePlane.RUNTIME,
              len({item.metric_id for item in observability.metrics}) == len(observability.metrics),
              len({item.metric_id for item in observability.metrics}), len(observability.metrics),
              "metric identities are unique"),
    )


__all__ = [
    "audit_release_assurance_observability",
    "build_release_assurance_observability",
]
