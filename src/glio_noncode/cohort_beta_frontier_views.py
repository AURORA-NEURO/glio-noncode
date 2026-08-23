"""Review-safe projections that retain context, state, and policy disposition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_policy import CohortBetaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReviewRow:
    operation: str
    record_id: str
    state: str
    disposition: str
    reason: str
    prohibited_claim_count: int
    result_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReviewView:
    rows: tuple[CohortBetaFrontierReviewRow, ...]
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_review_view(evaluation: CohortBetaFrontierEvaluation, policy: CohortBetaFrontierPolicy, context_key: str) -> CohortBetaFrontierReviewView:
    rows = tuple(CohortBetaFrontierReviewRow(item.operation, item.record_id, item.observed_state.value, policy.for_record(item.record_id).disposition.value, "matched expected state" if item.accepted else "state mismatch", len(policy.for_record(item.record_id).prohibited_claims), item.content_address) for item in evaluation.rows)
    return CohortBetaFrontierReviewView(rows, context_key, content_hash({"rows": rows, "context_key": context_key}, prefix="review-view"))


__all__ = ["CohortBetaFrontierReviewRow", "CohortBetaFrontierReviewView", "build_cohort_beta_frontier_review_view"]
