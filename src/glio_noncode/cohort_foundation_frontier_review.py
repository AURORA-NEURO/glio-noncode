"""Review queue projections for incomplete and foreign-context controls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_policy import CohortFoundationDisposition, CohortFoundationPolicy
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation


class CohortFoundationReviewSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class CohortFoundationReviewItem:
    review_id: str
    record_id: str
    operation: str
    severity: CohortFoundationReviewSeverity
    disposition: CohortFoundationDisposition
    issue_codes: tuple[str, ...]
    reviewer_roles: tuple[str, ...]
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationReviewQueue:
    queue_id: str
    items: tuple[CohortFoundationReviewItem, ...]
    accepted: bool
    content_address: str

    @property
    def review_ids(self) -> tuple[str, ...]:
        return tuple(item.review_id for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_review_queue(evaluation: CohortFoundationEvaluation, policy: CohortFoundationPolicy) -> CohortFoundationReviewQueue:
    items = []
    for execution in evaluation.executions:
        decision = policy.decision_for(execution.record_id)
        if decision.disposition is CohortFoundationDisposition.ALLOW_DESCRIPTIVE:
            continue
        severity = CohortFoundationReviewSeverity.HIGH if decision.disposition is CohortFoundationDisposition.QUARANTINE else CohortFoundationReviewSeverity.MEDIUM if execution.issues else CohortFoundationReviewSeverity.LOW
        roles = ("context_reviewer", "data_reviewer") if decision.disposition is CohortFoundationDisposition.QUARANTINE else ("cohort_reviewer", "methods_reviewer")
        action = "confirm foreign-context quarantine" if decision.disposition is CohortFoundationDisposition.QUARANTINE else "review coverage and retain limitations"
        body = {"record_id": execution.record_id, "operation": execution.operation, "severity": severity, "disposition": decision.disposition, "issues": execution.issues}
        items.append(CohortFoundationReviewItem(content_hash((execution.record_id, "review"), prefix="review"), execution.record_id, execution.operation.value, severity, decision.disposition, execution.issues, roles, action, content_hash(body)))
    body = {"queue_id": "cohort-foundation-frontier-review", "items": items}
    return CohortFoundationReviewQueue(body["queue_id"], tuple(items), True, content_hash(body))


__all__ = ["CohortFoundationReviewItem", "CohortFoundationReviewQueue", "CohortFoundationReviewSeverity", "build_cohort_foundation_frontier_review_queue"]
