"""Deterministic events and metrics for service-release operations."""

from __future__ import annotations

from .service_release_contracts import (
    SERVICE_RELEASE_OBSERVABILITY_EVENT_COUNT,
    SERVICE_RELEASE_OBSERVABILITY_METRIC_COUNT,
    ServiceReleaseEvent,
    ServiceReleaseMetric,
    ServiceReleaseObservability,
    ServiceReleasePlane,
    ServiceReleaseSnapshot,
    check,
)
from .serialization import content_hash

_EVENT_TYPES = (
    "source-read", "surface-registered", "artifact-addressed", "dependency-checked",
    "gate-evaluated", "index-built", "summary-built", "certification-built",
    "graph-built", "plan-built", "view-built", "boundary-checked", "release-ready",
)


def build_service_release_observability(snapshot: ServiceReleaseSnapshot) -> ServiceReleaseObservability:
    """Build a stable thirteen-event trace for every service surface."""

    events: list[ServiceReleaseEvent] = []
    sequence = 0
    for surface in snapshot.surfaces:
        previous = surface.source_address
        for event_type in _EVENT_TYPES:
            sequence += 1
            output = content_hash(
                {"surface_id": surface.surface_id, "event_type": event_type,
                 "sequence": sequence, "input_address": previous},
                prefix="service-release-observability-output",
            )
            body = {
                "sequence": sequence,
                "event_id": f"event:{sequence:03d}:{surface.surface_id}:{event_type}",
                "event_type": event_type,
                "surface_id": surface.surface_id,
                "input_address": previous,
                "output_address": output,
            }
            events.append(ServiceReleaseEvent(
                **body, content_address=content_hash(body, prefix="service-release-event")
            ))
            previous = output
    metrics: list[ServiceReleaseMetric] = []
    metric_specs = (("row_count", "rows"), ("artifact_count", "artifacts"),
                    ("accepted", "boolean"), ("dependency_order", "ordinal"))
    for surface in snapshot.surfaces:
        values = {"row_count": surface.row_count, "artifact_count": surface.artifact_count,
                  "accepted": int(surface.accepted), "dependency_order": surface.dependency_order}
        for name, unit in metric_specs:
            body = {"metric_id": f"metric:{surface.surface_id}:{name}",
                    "surface_id": surface.surface_id, "name": name,
                    "value": values[name], "unit": unit}
            metrics.append(ServiceReleaseMetric(
                **body, content_address=content_hash(body, prefix="service-release-metric")
            ))
    accepted = (snapshot.accepted
                and len(events) == SERVICE_RELEASE_OBSERVABILITY_EVENT_COUNT
                and len(metrics) == SERVICE_RELEASE_OBSERVABILITY_METRIC_COUNT
                and tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1)))
    body = {"bundle_id": snapshot.bundle_id, "events": events, "metrics": metrics, "accepted": accepted}
    return ServiceReleaseObservability(
        snapshot.bundle_id, tuple(events), tuple(metrics), accepted,
        content_hash(body, prefix="service-release-observability"),
    )


def audit_service_release_observability(observability: ServiceReleaseObservability) -> tuple:
    """Audit event numbering, metric identity, and trace continuity."""

    events = observability.events
    return (
        check("observability:event-count", ServiceReleasePlane.OBSERVABILITY,
              len(events) == SERVICE_RELEASE_OBSERVABILITY_EVENT_COUNT, len(events),
              SERVICE_RELEASE_OBSERVABILITY_EVENT_COUNT, "event denominator is conserved"),
        check("observability:metric-count", ServiceReleasePlane.OBSERVABILITY,
              len(observability.metrics) == SERVICE_RELEASE_OBSERVABILITY_METRIC_COUNT,
              len(observability.metrics), SERVICE_RELEASE_OBSERVABILITY_METRIC_COUNT,
              "metric denominator is conserved"),
        check("observability:sequence", ServiceReleasePlane.OBSERVABILITY,
              tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1)),
              tuple(item.sequence for item in events[:3]), "one-based contiguous sequence",
              "events retain deterministic order"),
        check("observability:event-identities", ServiceReleasePlane.OBSERVABILITY,
              len({item.event_id for item in events}) == len(events),
              len({item.event_id for item in events}), len(events),
              "event identifiers are unique"),
        check("observability:metric-identities", ServiceReleasePlane.OBSERVABILITY,
              len({item.metric_id for item in observability.metrics}) == len(observability.metrics),
              len({item.metric_id for item in observability.metrics}), len(observability.metrics),
              "metric identifiers are unique"),
    )


__all__ = ["audit_service_release_observability", "build_service_release_observability"]
