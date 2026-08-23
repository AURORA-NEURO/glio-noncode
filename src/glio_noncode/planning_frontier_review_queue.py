"""Review queue projection for held planning scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningReviewQueue:
    items: tuple[dict[str, Any], ...]
    held_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_review_queue(evaluation: PlanningEvaluation) -> PlanningReviewQueue:
    items = tuple({"queue_id": f"review:{item.record_id}", "record_id": item.record_id, "operation": item.operation.value, "state": item.observed_state.value, "issue_codes": item.issue_codes, "priority": "blocking" if item.observed_state.value == "blocked" else "normal"} for item in evaluation.executions if item.observed_state.value != "ready_for_review")
    body = {"items": items, "held_count": len(items), "accepted": all(item["queue_id"] for item in items)}
    return PlanningReviewQueue(items, len(items), body["accepted"], content_hash(body, prefix="planning-review-queue"))


__all__ = ["PlanningReviewQueue", "build_planning_review_queue"]
