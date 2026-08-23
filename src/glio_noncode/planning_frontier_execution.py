"""Execution plan and state transition ledger for planning runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture, PlanningState
from .planning_frontier_operations import run_planning_operation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningTransition:
    record_id: str
    before: str
    after: str
    allowed: bool
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningExecutionPlan:
    plan_id: str
    ordered_records: tuple[str, ...]
    transitions: tuple[PlanningTransition, ...]
    operation_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


ALLOWED_TRANSITIONS = {
    "ready_for_review": {"ready_for_review", "review"},
    "review": {"review", "blocked", "abstained"},
    "blocked": {"blocked", "review"},
    "rejected": {"rejected", "review"},
    "abstained": {"abstained", "review"},
}


def build_planning_execution_plan(fixture: PlanningFixture, evaluation: PlanningEvaluation, *, plan_id: str = "planning-execution-plan") -> PlanningExecutionPlan:
    transitions = []
    operation_counts: dict[str, int] = {}
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        before = record.expected_state.value
        after = execution.observed_state.value
        allowed = after in ALLOWED_TRANSITIONS.get(before, set())
        body = {"record_id": record.record_id, "before": before, "after": after, "allowed": allowed, "issue_codes": execution.issue_codes}
        transitions.append(PlanningTransition(**body, content_address=content_hash(body, prefix="planning-transition")))
        operation_counts[record.operation.value] = operation_counts.get(record.operation.value, 0) + 1
    ordered = tuple(item.record_id for item in fixture.records)
    accepted = bool(ordered and len(transitions) == len(ordered) and all(item.allowed for item in transitions))
    body = {"plan_id": plan_id, "ordered_records": ordered, "transitions": tuple(transitions), "operation_counts": operation_counts, "accepted": accepted}
    return PlanningExecutionPlan(plan_id, ordered, tuple(transitions), operation_counts, accepted, content_hash(body, prefix="planning-execution-plan"))


__all__ = ["ALLOWED_TRANSITIONS", "PlanningExecutionPlan", "PlanningTransition", "build_planning_execution_plan"]
