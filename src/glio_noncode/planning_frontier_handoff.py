"""Reviewer handoff package for planning evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .planning_frontier_governance import PlanningClaimBoundary, build_planning_claim_boundary
from .planning_frontier_review_queue import PlanningReviewQueue, build_planning_review_queue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningHandoff:
    handoff_id: str
    fixture_id: str
    summary: dict[str, Any]
    queue: PlanningReviewQueue
    claim_boundary: PlanningClaimBoundary
    reviewer_actions: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_handoff(fixture: PlanningFixture, evaluation: PlanningEvaluation, *, handoff_id: str = "planning-handoff") -> PlanningHandoff:
    queue = build_planning_review_queue(evaluation)
    boundary = build_planning_claim_boundary()
    summary = {
        "record_count": len(evaluation.executions),
        "ready_count": sum(item.observed_state.value == "ready_for_review" for item in evaluation.executions),
        "held_count": queue.held_count,
        "operation_count": len(fixture.operations),
        "fixture_address": fixture.content_address,
    }
    actions = (
        "confirm exact context before reviewing evidence",
        "inspect issue codes before changing a disposition",
        "review foreign-context rows as blocked",
        "review power assumptions and replicate shortfalls",
        "retain excluded-use boundary in downstream reports",
    )
    body = {"handoff_id": handoff_id, "fixture_id": fixture.fixture_id, "summary": summary, "queue": queue, "claim_boundary": boundary, "reviewer_actions": actions, "accepted": bool(queue.accepted and boundary.accepted)}
    return PlanningHandoff(**body, content_address=content_hash(body, prefix="planning-handoff"))


__all__ = ["PlanningHandoff", "build_planning_handoff"]
