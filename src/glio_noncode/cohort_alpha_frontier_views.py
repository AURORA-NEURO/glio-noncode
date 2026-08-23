"""Stable read views for summaries, controls, and review work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy, CohortAlphaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierViewRow:
    view_id: str
    operation: str
    record_id: str
    state: str
    disposition: str
    visible: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierViewSet:
    views: tuple[CohortAlphaFrontierViewRow, ...]
    publish_view_count: int
    review_view_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_views(evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy, review: CohortAlphaFrontierReviewQueue) -> CohortAlphaFrontierViewSet:
    review_ids = {item.record_id for item in review.items}
    rows = tuple(CohortAlphaFrontierViewRow("publish" if policy.for_record(row.record_id).disposition.value == "publish" else "review", row.operation, row.record_id, row.observed_state.value, policy.for_record(row.record_id).disposition.value, row.record_id not in review_ids, content_hash({"record_id": row.record_id, "view": "publish" if row.record_id not in review_ids else "review"}, prefix="alpha-view")) for row in evaluation.rows)
    return CohortAlphaFrontierViewSet(rows, sum(item.view_id == "publish" for item in rows), sum(item.view_id == "review" for item in rows), len(rows) == len(evaluation.rows) and all(item.visible == (item.view_id == "publish") for item in rows), content_hash(rows, prefix="alpha-views"))


__all__ = ["CohortAlphaFrontierViewRow", "CohortAlphaFrontierViewSet", "build_cohort_alpha_frontier_views"]
