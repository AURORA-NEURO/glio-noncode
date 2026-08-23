"""Claim and execution policy gate for coordination operations."""

from __future__ import annotations

from .coordination_architecture_contracts import (
    COORDINATION_BOUNDARY,
    COORDINATION_CONTEXT,
    CoordinationCase,
    CoordinationOperationSpec,
    CoordinationPolicyDecision,
    CoordinationState,
    addressed,
)


def evaluate_coordination_policy(case: CoordinationCase, spec: CoordinationOperationSpec) -> CoordinationPolicyDecision:
    reasons: list[str] = []
    if case.context_key != COORDINATION_CONTEXT or case.payload.get("declared_context_key") != COORDINATION_CONTEXT:
        reasons.append("context_not_supported")
    if case.payload.get("claim_boundary") != COORDINATION_BOUNDARY:
        reasons.append("claim_boundary_mismatch")
    if case.payload.get("network_requested"):
        reasons.append("network_not_allowed")
    if case.payload.get("public_aggregate_only") is not True:
        reasons.append("public_aggregate_scope_required")
    if case.operation_id != spec.operation_id:
        reasons.append("operation_not_declared")
    allowed = not reasons
    body = {
        "decision_id": f"policy:{case.case_id}",
        "state": CoordinationState.ACCEPTED if allowed else CoordinationState.REVIEW,
        "allowed": allowed,
        "reasons": tuple(sorted(set(reasons))),
        "claim_boundary": COORDINATION_BOUNDARY,
    }
    return CoordinationPolicyDecision(**body, content_address=addressed(body, "coordination-policy"))


__all__ = ["evaluate_coordination_policy"]
