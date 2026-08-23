"""Expected-state reconciliation with explicit mismatch records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .cohort_beta_frontier_policy import CohortBetaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReconciliationItem:
    record_id: str
    operation: str
    expected_state: str
    observed_state: str
    matched: bool
    policy_disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReconciliation:
    items: tuple[CohortBetaFrontierReconciliationItem, ...]
    reconciled: bool
    mismatch_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_cohort_beta_frontier(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, policy: CohortBetaFrontierPolicy) -> CohortBetaFrontierReconciliation:
    expected = {item.record_id: item for item in fixture.records}
    items = []
    for row in evaluation.rows:
        decision = policy.for_record(row.record_id)
        match = row.expected_state.value == row.observed_state.value
        body = {"record_id": row.record_id, "expected_state": row.expected_state.value, "observed_state": row.observed_state.value, "matched": match, "disposition": decision.disposition.value}
        items.append(CohortBetaFrontierReconciliationItem(row.record_id, row.operation, row.expected_state.value, row.observed_state.value, match, decision.disposition.value, content_hash(body, prefix="reconciliation-item")))
    values = tuple(items)
    body = {"items": values, "fixture_record_count": len(expected)}
    return CohortBetaFrontierReconciliation(values, all(item.matched for item in values) and len(values) == len(expected), sum(not item.matched for item in values), content_hash(body, prefix="reconciliation"))


__all__ = ["CohortBetaFrontierReconciliation", "CohortBetaFrontierReconciliationItem", "reconcile_cohort_beta_frontier"]
