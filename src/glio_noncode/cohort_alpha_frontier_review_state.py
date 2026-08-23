"""Review state receipt for queue age, priority, and disposition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewState:
    queue_id: str
    open_count: int
    highest_priority: int
    required_evidence_count: int
    state: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_review_state(queue: CohortAlphaFrontierReviewQueue) -> CohortAlphaFrontierReviewState:
    highest = max((item.priority for item in queue.items), default=0)
    evidence = sum(len(item.required_evidence) for item in queue.items)
    state = "open" if queue.open_count else "closed"
    body = {"queue": "cohort-alpha-frontier-review", "open": queue.open_count, "highest": highest, "evidence": evidence, "state": state}
    return CohortAlphaFrontierReviewState(body["queue"], queue.open_count, highest, evidence, state, queue.accepted and (queue.open_count == 0 or highest in {1, 2}), content_hash(body, prefix="alpha-review-state"))


__all__ = ["CohortAlphaFrontierReviewState", "build_cohort_alpha_frontier_review_state"]
