"""Reconcile expected fixture states, executions, and policy dispositions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_policy import CohortFoundationDisposition, CohortFoundationPolicy
from .cohort_foundation_frontier_public_data import CohortFoundationFixture


@dataclass(frozen=True, slots=True)
class CohortFoundationReconciliationItem:
    record_id: str
    expected_state: str
    actual_state: str
    expected_issues: tuple[str, ...]
    actual_issues: tuple[str, ...]
    expected_disposition: str
    actual_disposition: str
    state_match: bool
    issue_match: bool
    disposition_match: bool
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state_match and self.issue_match and self.disposition_match

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class CohortFoundationReconciliation:
    fixture_id: str
    items: tuple[CohortFoundationReconciliationItem, ...]
    reconciled: bool
    mismatches: tuple[str, ...]
    content_address: str

    def for_record(self, record_id: str) -> CohortFoundationReconciliationItem:
        return next(item for item in self.items if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_cohort_foundation_frontier(fixture: CohortFoundationFixture, evaluation: CohortFoundationEvaluation, policy: CohortFoundationPolicy) -> CohortFoundationReconciliation:
    expected = {item.record_id: item for item in fixture.records}
    actual = {item.record_id: item for item in evaluation.executions}
    items = []
    for record_id in sorted(expected):
        record = expected[record_id]
        execution = actual[record_id]
        decision = policy.decision_for(record_id)
        expected_disposition = CohortFoundationDisposition.ALLOW_DESCRIPTIVE.value if record.expected_state == "supported" else CohortFoundationDisposition.QUARANTINE.value if record.expected_state == "out_of_domain" else CohortFoundationDisposition.REVIEW.value
        issue_match = set(record.expected_issues) <= set(execution.issues) or (not record.expected_issues and not execution.issues)
        body = {"record_id": record_id, "expected_state": record.expected_state, "actual_state": execution.actual_state, "expected_issues": record.expected_issues, "actual_issues": execution.issues, "decision": decision.disposition}
        items.append(CohortFoundationReconciliationItem(record_id, record.expected_state, execution.actual_state, record.expected_issues, execution.issues, expected_disposition, decision.disposition.value, record.expected_state == execution.actual_state, issue_match, expected_disposition == decision.disposition.value, content_hash(body)))
    mismatches = tuple(item.record_id for item in items if not item.accepted)
    body = {"fixture_id": fixture.fixture_id, "items": items, "mismatches": mismatches}
    return CohortFoundationReconciliation(fixture.fixture_id, tuple(items), not mismatches, mismatches, content_hash(body))


__all__ = ["CohortFoundationReconciliation", "CohortFoundationReconciliationItem", "reconcile_cohort_foundation_frontier"]
