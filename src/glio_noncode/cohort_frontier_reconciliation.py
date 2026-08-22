"""Reconcile cohort fixture expectations with replay and policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_fixture_eval import CohortFrontierEvaluation
from .cohort_frontier_policy import CohortFrontierDecision, CohortFrontierPolicy
from .cohort_frontier_public_data import CohortFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    decision: CohortFrontierDecision
    content_address: str

    @property
    def reconciled(self) -> bool:
        return self.state_match and self.issue_match

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"reconciled": self.reconciled}


@dataclass(frozen=True, slots=True)
class CohortFrontierReconciliation:
    fixture_id: str
    items: tuple[CohortFrontierReconciliationItem, ...]
    evaluation_accepted: bool
    policy_decisions: tuple[str, ...]
    reconciled: bool
    content_address: str

    @property
    def mismatched_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.items if not item.reconciled)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"mismatched_record_ids": list(self.mismatched_record_ids)}


def reconcile_cohort_frontier(fixture: CohortFrontierFixture, evaluation: CohortFrontierEvaluation, policy: CohortFrontierPolicy) -> CohortFrontierReconciliation:
    decisions = {item.operation: item for item in policy.decide(evaluation)}
    items: list[CohortFrontierReconciliationItem] = []
    for record in fixture.records:
        execution = evaluation.execution_map()[record.record_id]
        body = {"record_id": record.record_id, "expected_state": record.expected_state, "observed_state": execution.state, "expected_issue_codes": tuple(sorted(record.expected_issue_codes)), "observed_issue_codes": execution.issue_codes, "state_match": record.expected_state == execution.state, "issue_match": tuple(sorted(record.expected_issue_codes)) == execution.issue_codes, "decision": decisions[record.operation].decision}
        items.append(CohortFrontierReconciliationItem(**body, content_address=content_hash(body)))
    body = {"fixture_id": fixture.fixture_id, "items": tuple(items), "evaluation_accepted": evaluation.accepted, "policy_decisions": tuple(item.decision.value for item in decisions.values()), "reconciled": all(item.reconciled for item in items) and evaluation.accepted}
    return CohortFrontierReconciliation(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierReconciliation", "CohortFrontierReconciliationItem", "reconcile_cohort_frontier"]
