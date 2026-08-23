"""Review closure receipt proving non-publishable paths stay outside output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReviewQueue
from .cohort_alpha_frontier_publication_filter import CohortAlphaFrontierPublicationFilter
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewClosureRow:
    record_id: str
    queued: bool
    publishable: bool
    isolated: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewClosure:
    rows: tuple[CohortAlphaFrontierReviewClosureRow, ...]
    closed_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def verify_cohort_alpha_frontier_review_closure(queue: CohortAlphaFrontierReviewQueue, publication: CohortAlphaFrontierPublicationFilter) -> CohortAlphaFrontierReviewClosure:
    queued = {item.record_id for item in queue.items}
    rows = tuple(CohortAlphaFrontierReviewClosureRow(item.record_id, item.record_id in queued, item.eligible, item.record_id in queued and not item.eligible, content_hash({"record_id": item.record_id, "queued": item.record_id in queued, "publishable": item.eligible, "isolated": item.record_id in queued and not item.eligible}, prefix="alpha-review-closure")) for item in publication.rows)
    return CohortAlphaFrontierReviewClosure(rows, sum(item.isolated for item in rows), len(rows) == 16 and all((item.queued and not item.publishable) or (not item.queued and item.publishable) for item in rows), content_hash(rows, prefix="alpha-review-closure-report"))


__all__ = ["CohortAlphaFrontierReviewClosure", "CohortAlphaFrontierReviewClosureRow", "verify_cohort_alpha_frontier_review_closure"]
