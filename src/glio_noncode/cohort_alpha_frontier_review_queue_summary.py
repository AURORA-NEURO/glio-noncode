"""Review queue summary grouped by priority and operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewQueueSummary:
    total: int
    priority_one: int
    priority_two: int
    operations: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def summarize_cohort_alpha_frontier_review_queue(queue: CohortAlphaFrontierReviewQueue) -> CohortAlphaFrontierReviewQueueSummary:
    operations = {operation: sum(item.operation == operation for item in queue.items) for operation in ("C09", "C10", "C11", "C12")}
    body = {"total": len(queue.items), "priority_one": sum(item.priority == 1 for item in queue.items), "priority_two": sum(item.priority == 2 for item in queue.items), "operations": operations}
    return CohortAlphaFrontierReviewQueueSummary(body["total"], body["priority_one"], body["priority_two"], operations, queue.accepted and body["total"] == 12 and sum(operations.values()) == 12, content_hash(body, prefix="alpha-review-queue-summary"))


__all__ = ["CohortAlphaFrontierReviewQueueSummary", "summarize_cohort_alpha_frontier_review_queue"]
