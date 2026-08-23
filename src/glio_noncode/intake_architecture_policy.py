"""Policy receipts for scope, consent, anomaly, and completeness boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .intake_architecture_contracts import IntakeArchitectureCase, IntakeArchitectureState, addressed


@dataclass(frozen=True, slots=True)
class IntakeArchitecturePolicyDecision:
    decision_id: str
    state: IntakeArchitectureState
    allowed: bool
    reasons: tuple[str, ...]
    boundary: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "state": self.state.value,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "boundary": self.boundary,
            "content_address": self.content_address,
        }


def evaluate_intake_policy(case: IntakeArchitectureCase) -> IntakeArchitecturePolicyDecision:
    payload = case.payload
    reasons: list[str] = []
    if payload.get("public_aggregate_only") is not True:
        reasons.append("public_aggregate_scope_required")
    if payload.get("context_key") != case.context_key:
        reasons.append("context_mismatch")
    policy = payload.get("policy")
    if isinstance(policy, Mapping) and policy.get("patient_level_data") is not False:
        reasons.append("patient_level_data_not_permitted")
    if payload.get("malformed") is True:
        reasons.append("malformed_input_requires_review")
    allowed = not reasons
    state = IntakeArchitectureState.ACCEPTED if allowed else IntakeArchitectureState.REVIEW
    body = {"decision_id": f"policy:{case.case_id}", "state": state, "allowed": allowed, "reasons": tuple(sorted(set(reasons))), "boundary": "public aggregate intake only"}
    return IntakeArchitecturePolicyDecision(**body, content_address=addressed(body, "intake-policy"))


__all__ = ["IntakeArchitecturePolicyDecision", "evaluate_intake_policy"]
