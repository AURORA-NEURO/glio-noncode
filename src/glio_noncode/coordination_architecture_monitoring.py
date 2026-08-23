"""Context, drift, and out-of-domain observation projections."""

from __future__ import annotations

from .coordination_architecture_contracts import (
    COORDINATION_CONTEXT,
    CoordinationFixture,
    CoordinationObservation,
    CoordinationState,
    addressed,
)


def build_coordination_observations(fixture: CoordinationFixture) -> tuple[CoordinationObservation, ...]:
    values = []
    for spec in fixture.operations:
        body = {
            "observation_id": f"observation:{spec.operation_id}",
            "operation_id": spec.operation_id,
            "observed_context": COORDINATION_CONTEXT,
            "reference_rate": 1.0,
            "drift_score": 0.0,
            "out_of_domain": False,
            "state": CoordinationState.ACCEPTED,
        }
        values.append(CoordinationObservation(**body, content_address=addressed(body, "coordination-observation")))
    return tuple(values)


def audit_coordination_observations(observations: tuple[CoordinationObservation, ...], expected_count: int = 16) -> tuple[str, ...]:
    issues: list[str] = []
    if len(observations) != expected_count:
        issues.append("observation_count_mismatch")
    if any(item.observed_context != COORDINATION_CONTEXT for item in observations):
        issues.append("observation_context_mismatch")
    if any(item.out_of_domain or item.drift_score > 0.25 for item in observations):
        issues.append("drift_boundary_exceeded")
    if any(not 0.0 <= item.reference_rate <= 1.0 for item in observations):
        issues.append("reference_rate_out_of_range")
    return tuple(sorted(set(issues)))


__all__ = ["build_coordination_observations", "audit_coordination_observations"]
