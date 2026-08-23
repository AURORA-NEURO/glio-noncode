"""Deterministic fallback routing for held coordination cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_contracts import CoordinationCase, CoordinationState, addressed


@dataclass(frozen=True, slots=True)
class CoordinationFallbackRoute:
    case_id: str
    selected_route: str
    state: CoordinationState
    retryable: bool
    reasons: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "selected_route": self.selected_route,
            "state": self.state,
            "retryable": self.retryable,
            "reasons": self.reasons,
            "content_address": self.content_address,
        }


def route_coordination_fallback(case: CoordinationCase, issue_codes: tuple[str, ...]) -> CoordinationFallbackRoute:
    if not issue_codes:
        route, state, retryable = "primary_local", CoordinationState.ACCEPTED, False
    elif "foreign_context" in issue_codes:
        route, state, retryable = "manual_context_review", CoordinationState.REVIEW, False
    elif "budget_exceeded" in issue_codes:
        route, state, retryable = "capacity_review", CoordinationState.REVIEW, True
    elif "contract_mismatch" in issue_codes:
        route, state, retryable = "contract_repair_review", CoordinationState.REVIEW, False
    else:
        route, state, retryable = "manual_boundary_review", CoordinationState.REVIEW, False
    body = {
        "case_id": case.case_id,
        "selected_route": route,
        "state": state,
        "retryable": retryable,
        "reasons": issue_codes,
    }
    return CoordinationFallbackRoute(**body, content_address=addressed(body, "coordination-fallback"))


__all__ = ["CoordinationFallbackRoute", "route_coordination_fallback"]
