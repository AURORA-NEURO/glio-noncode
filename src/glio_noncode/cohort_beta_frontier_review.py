"""Review queue built from partial, contradictory, and quarantined paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_policy import CohortBetaFrontierDisposition, CohortBetaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReviewItem:
    record_id: str
    operation: str
    priority: int
    reason: str
    required_evidence: tuple[str, ...]
    disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReviewQueue:
    items: tuple[CohortBetaFrontierReviewItem, ...]
    accepted: bool
    open_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_review_queue(evaluation: CohortBetaFrontierEvaluation, policy: CohortBetaFrontierPolicy) -> CohortBetaFrontierReviewQueue:
    items: list[CohortBetaFrontierReviewItem] = []
    for row in evaluation.rows:
        decision = policy.for_record(row.record_id)
        if decision.disposition is CohortBetaFrontierDisposition.PUBLISH:
            continue
        priority = 1 if decision.disposition is CohortBetaFrontierDisposition.QUARANTINE else 2
        required = ("context receipt", "callable-space accounting") if row.operation in {"C05", "C06"} else ("matched comparator", "definition version receipt")
        body = {"record_id": row.record_id, "operation": row.operation, "priority": priority, "reason": decision.rationale, "required": required}
        items.append(CohortBetaFrontierReviewItem(row.record_id, row.operation, priority, decision.rationale, required, decision.disposition.value, content_hash(body, prefix="review-item")))
    values = tuple(sorted(items, key=lambda item: (item.priority, item.operation, item.record_id)))
    return CohortBetaFrontierReviewQueue(values, all(item.priority in {1, 2} for item in values), len(values), content_hash(values, prefix="review-queue"))


__all__ = ["CohortBetaFrontierReviewItem", "CohortBetaFrontierReviewQueue", "build_cohort_beta_frontier_review_queue"]
