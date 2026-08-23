"""Review priority and service targets for retained control paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_review import CohortFoundationReviewQueue


@dataclass(frozen=True, slots=True)
class CohortFoundationReviewSlaItem:
    review_id: str
    priority: str
    target_hours: int
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationReviewSlaReport:
    report_id: str
    items: tuple[CohortFoundationReviewSlaItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_review_sla(queue: CohortFoundationReviewQueue) -> CohortFoundationReviewSlaReport:
    items = []
    for item in queue.items:
        priority = "urgent" if item.severity.value == "high" else "standard"
        hours = 4 if priority == "urgent" else 24
        rationale = "foreign context requires isolation confirmation" if priority == "urgent" else "incomplete descriptive evidence requires review"
        items.append(CohortFoundationReviewSlaItem(item.review_id, priority, hours, rationale, content_hash((item.review_id, priority, hours, rationale))))
    body = {"report_id": "cohort-foundation-frontier-review-sla", "items": items}
    return CohortFoundationReviewSlaReport(body["report_id"], tuple(items), all(item.target_hours > 0 for item in items), content_hash(body))


__all__ = ["CohortFoundationReviewSlaItem", "CohortFoundationReviewSlaReport", "build_cohort_foundation_frontier_review_sla"]
