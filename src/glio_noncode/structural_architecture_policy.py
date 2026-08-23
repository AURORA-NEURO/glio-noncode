"""Publication and review policy for the composed structural boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .structural_architecture_contracts import (
    STRUCTURAL_ARCHITECTURE_CONTEXT,
    StructuralArchitectureCase,
    StructuralArchitectureScenario,
    StructuralArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class StructuralArchitecturePolicyDecision:
    case_id: str
    allowed: bool
    state: StructuralArchitectureState
    reason_codes: tuple[str, ...]
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "allowed": self.allowed,
            "state": self.state.value,
            "reason_codes": list(self.reason_codes),
            "required_action": self.required_action,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class StructuralArchitecturePolicyReport:
    fixture_id: str
    decisions: tuple[StructuralArchitecturePolicyDecision, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "decisions": [item.to_dict() for item in self.decisions],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def evaluate_structural_architecture_policy(
    case: StructuralArchitectureCase,
) -> StructuralArchitecturePolicyDecision:
    """Decide whether a case can enter the accepted execution path."""

    reasons: list[str] = []
    if case.context_key != STRUCTURAL_ARCHITECTURE_CONTEXT:
        reasons.append("context_mismatch")
    if not case.source_ids:
        reasons.append("source_missing")
    if not case.payload:
        reasons.append("payload_empty")
    if case.scenario is StructuralArchitectureScenario.FOREIGN_CONTEXT:
        reasons.append("foreign_context")
    elif case.scenario is StructuralArchitectureScenario.MALFORMED_INPUT:
        reasons.append("malformed_input")
    elif case.scenario is StructuralArchitectureScenario.DUPLICATE_IDENTITY:
        reasons.append("duplicate_identity")
    if case.scenario is not StructuralArchitectureScenario.POSITIVE and not reasons:
        reasons.append("control_case")
    allowed = case.scenario is StructuralArchitectureScenario.POSITIVE and not reasons
    state = StructuralArchitectureState.ACCEPTED if allowed else StructuralArchitectureState.REVIEW
    action = (
        "execute and retain addressed result"
        if allowed
        else "hold, diagnose, and require bounded review"
    )
    body = {
        "case_id": case.case_id,
        "allowed": allowed,
        "state": state,
        "reason_codes": tuple(sorted(set(reasons))),
        "required_action": action,
    }
    return StructuralArchitecturePolicyDecision(
        **body,
        content_address=addressed(body, "structural-policy"),
    )


def evaluate_structural_architecture_policies(
    fixture_id: str,
    cases: tuple[StructuralArchitectureCase, ...],
) -> StructuralArchitecturePolicyReport:
    decisions = tuple(evaluate_structural_architecture_policy(case) for case in cases)
    accepted = len(decisions) == len(cases) and all(
        decision.state is StructuralArchitectureState.ACCEPTED
        for decision, case in zip(decisions, cases, strict=True)
        if case.scenario is StructuralArchitectureScenario.POSITIVE
    )
    body = {"fixture_id": fixture_id, "decisions": decisions, "accepted": accepted}
    return StructuralArchitecturePolicyReport(
        fixture_id=fixture_id,
        decisions=decisions,
        accepted=accepted,
        content_address=addressed(body, "structural-policy-report"),
    )


__all__ = [
    "StructuralArchitecturePolicyDecision",
    "StructuralArchitecturePolicyReport",
    "evaluate_structural_architecture_policy",
    "evaluate_structural_architecture_policies",
]
