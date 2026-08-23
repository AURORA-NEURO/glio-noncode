"""Declared negative-boundary rehearsals for the planning adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_adapters import build_planning_adapters, execute_planning_adapter
from .planning_frontier_contracts import PlanningOperation
from .planning_frontier_public_data import default_planning_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningFailureCase:
    case_id: str
    operation: str
    expected_state: str
    observed_state: str
    expected_issue: str
    observed_issues: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningFailureReport:
    cases: tuple[PlanningFailureCase, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_failure_report() -> PlanningFailureReport:
    registry = build_planning_adapters()
    payloads = (
        ("eligibility-empty", PlanningOperation.MODEL_ELIGIBILITY, {}, "rejected", "invalid_payload"),
        ("guide-empty", PlanningOperation.GUIDE_OLIGO, {}, "rejected", "invalid_payload"),
        ("controls-empty", PlanningOperation.CONTROLS_RANDOMIZATION, {}, "rejected", "invalid_payload"),
        ("power-empty", PlanningOperation.POWER_REPLICATION, {}, "rejected", "invalid_payload"),
    )
    cases = []
    for case_id, operation, payload, expected_state, expected_issue in payloads:
        result = execute_planning_adapter(registry, operation, payload)
        body = {
            "case_id": case_id,
            "operation": operation.value,
            "expected_state": expected_state,
            "observed_state": result.state.value,
            "expected_issue": expected_issue,
            "observed_issues": result.issue_codes,
            "passed": result.state.value == expected_state and expected_issue in result.issue_codes,
        }
        cases.append(PlanningFailureCase(**body, content_address=content_hash(body, prefix="planning-failure-case")))
    values = tuple(cases)
    return PlanningFailureReport(values, all(item.passed for item in values), content_hash(values, prefix="planning-failure"))


__all__ = ["PlanningFailureCase", "PlanningFailureReport", "build_planning_failure_report"]
