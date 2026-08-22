"""Reconcile fixture expectations with execution receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_policy import WorkspaceFrontierPolicy
from .workspace_frontier_public_data import WorkspaceFrontierFixture


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReconciliation:
    fixture_id: str
    items: tuple[WorkspaceFrontierReconciliationItem, ...]
    reconciled: bool
    mismatched_record_ids: tuple[str, ...]
    policy_decision_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_workspace_frontier(fixture: WorkspaceFrontierFixture, evaluation: WorkspaceFrontierEvaluation, policy: WorkspaceFrontierPolicy) -> WorkspaceFrontierReconciliation:
    expected = fixture.record_map()
    items = []
    for execution in evaluation.executions:
        record = expected[execution.record_id]
        body = {
            "record_id": record.record_id,
            "expected_state": record.expected_state,
            "observed_state": execution.state,
            "expected_issue_codes": tuple(sorted(record.expected_issue_codes)),
            "observed_issue_codes": execution.issue_codes,
            "accepted": record.expected_state == execution.state and tuple(sorted(record.expected_issue_codes)) == execution.issue_codes,
        }
        items.append(WorkspaceFrontierReconciliationItem(**body, content_address=content_hash(body)))
    decisions = policy.decide(evaluation)
    mismatched = tuple(item.record_id for item in items if not item.accepted)
    body = {"fixture_id": fixture.fixture_id, "items": tuple(items), "reconciled": not mismatched, "mismatched_record_ids": mismatched, "policy_decision_count": len(decisions)}
    return WorkspaceFrontierReconciliation(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierReconciliation", "WorkspaceFrontierReconciliationItem", "reconcile_workspace_frontier"]
