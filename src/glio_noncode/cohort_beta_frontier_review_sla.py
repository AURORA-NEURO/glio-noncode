"""Review service-level targets based on disposition severity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_review import CohortBetaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReviewSla:
    priority: int
    target_hours: int
    queue_count: int
    escalation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReviewSlaReport:
    targets: tuple[CohortBetaFrontierReviewSla, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_review_sla(queue: CohortBetaFrontierReviewQueue) -> CohortBetaFrontierReviewSlaReport:
    values = tuple(CohortBetaFrontierReviewSla(priority, 24 if priority == 1 else 72, sum(item.priority == priority for item in queue.items), "release owner" if priority == 1 else "operation owner", content_hash({"priority": priority, "count": sum(item.priority == priority for item in queue.items)}, prefix="review-sla")) for priority in (1, 2))
    return CohortBetaFrontierReviewSlaReport(values, all(item.target_hours > 0 for item in values), content_hash(values, prefix="review-sla-report"))


__all__ = ["CohortBetaFrontierReviewSla", "CohortBetaFrontierReviewSlaReport", "build_cohort_beta_frontier_review_sla"]
