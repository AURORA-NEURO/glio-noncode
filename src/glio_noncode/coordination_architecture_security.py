"""Privacy and security policy projections for local aggregate execution."""

from __future__ import annotations

from .coordination_architecture_contracts import (
    CoordinationCase,
    CoordinationSecurityDecision,
    CoordinationState,
    addressed,
)
from .module_fabric_support import contains_private_key


def evaluate_coordination_security(case: CoordinationCase) -> CoordinationSecurityDecision:
    private_key_detected = contains_private_key(case.payload)
    network_requested = bool(case.payload.get("network_requested"))
    reasons: list[str] = []
    if private_key_detected:
        reasons.append("private_key_detected")
    if network_requested:
        reasons.append("network_requested")
    if case.payload.get("public_aggregate_only") is not True:
        reasons.append("aggregate_scope_required")
    body = {
        "decision_id": f"security:{case.case_id}",
        "path_class": "public_aggregate_projection",
        "network_requested": network_requested,
        "private_key_detected": private_key_detected,
        "state": CoordinationState.ACCEPTED if not reasons else CoordinationState.REVIEW,
        "reasons": tuple(sorted(set(reasons))),
    }
    return CoordinationSecurityDecision(**body, content_address=addressed(body, "coordination-security"))


__all__ = ["evaluate_coordination_security"]
