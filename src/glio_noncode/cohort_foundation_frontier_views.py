"""Human-review projections that preserve exact operation ordering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_policy import CohortFoundationPolicy


@dataclass(frozen=True, slots=True)
class CohortFoundationReviewViewRow:
    record_id: str
    operation: str
    role: str
    expected_state: str
    actual_state: str
    disposition: str
    issue_codes: tuple[str, ...]
    source_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationReviewView:
    view_id: str
    context_key: str
    rows: tuple[CohortFoundationReviewViewRow, ...]
    facets: dict[str, tuple[str, ...]]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_review_view(evaluation: CohortFoundationEvaluation, policy: CohortFoundationPolicy, context_key: str) -> CohortFoundationReviewView:
    rows = []
    for execution in evaluation.executions:
        decision = policy.decision_for(execution.record_id)
        body = {"record_id": execution.record_id, "operation": execution.operation, "role": execution.role, "state": execution.actual_state, "disposition": decision.disposition, "issues": execution.issues}
        rows.append(CohortFoundationReviewViewRow(execution.record_id, execution.operation.value, execution.role.value, execution.expected_state, execution.actual_state, decision.disposition.value, execution.issues, len(execution.source_ids), content_hash(body)))
    rows = tuple(sorted(rows, key=lambda item: (item.operation, item.record_id)))
    facets = {"operation": tuple(sorted({item.operation for item in rows})), "state": tuple(sorted({item.actual_state for item in rows})), "disposition": tuple(sorted({item.disposition for item in rows})), "role": tuple(sorted({item.role for item in rows}))}
    body = {"view_id": "cohort-foundation-frontier-review", "context_key": context_key, "rows": rows, "facets": facets}
    return CohortFoundationReviewView(body["view_id"], context_key, rows, facets, content_hash(body))


__all__ = ["CohortFoundationReviewView", "CohortFoundationReviewViewRow", "build_cohort_foundation_frontier_review_view"]
