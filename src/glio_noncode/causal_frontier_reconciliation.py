"""Reconcile fixture expectations, execution receipts, and release state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_fixture_eval import CausalFrontierEvaluation
from .causal_frontier_policy import CausalFrontierDecision, CausalFrontierPolicy
from .causal_frontier_public_data import CausalFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    decision: CausalFrontierDecision
    content_address: str

    @property
    def reconciled(self) -> bool:
        return self.state_match and self.issue_match

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"reconciled": self.reconciled}


@dataclass(frozen=True, slots=True)
class CausalFrontierReconciliation:
    fixture_id: str
    items: tuple[CausalFrontierReconciliationItem, ...]
    evaluation_accepted: bool
    policy_decisions: tuple[str, ...]
    reconciled: bool
    content_address: str

    @property
    def mismatched_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.items if not item.reconciled)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"mismatched_record_ids": list(self.mismatched_record_ids)}


def reconcile_causal_frontier(
    fixture: CausalFrontierFixture,
    evaluation: CausalFrontierEvaluation,
    policy: CausalFrontierPolicy,
) -> CausalFrontierReconciliation:
    decisions = {item.operation: item for item in policy.decide(evaluation)}
    items: list[CausalFrontierReconciliationItem] = []
    for record in fixture.records:
        execution = evaluation.execution_map()[record.record_id]
        decision = decisions[record.operation]
        body = {
            "record_id": record.record_id,
            "expected_state": record.expected_state,
            "observed_state": execution.state,
            "expected_issue_codes": tuple(sorted(record.expected_issue_codes)),
            "observed_issue_codes": execution.issue_codes,
            "state_match": execution.state == record.expected_state,
            "issue_match": execution.issue_codes == tuple(sorted(record.expected_issue_codes)),
            "decision": decision.decision,
        }
        items.append(CausalFrontierReconciliationItem(**body, content_address=content_hash(body)))
    accepted = all(item.reconciled for item in items) and evaluation.accepted
    body = {
        "fixture_id": fixture.fixture_id,
        "items": tuple(items),
        "evaluation_accepted": evaluation.accepted,
        "policy_decisions": tuple(item.decision.value for item in decisions.values()),
        "reconciled": accepted,
    }
    return CausalFrontierReconciliation(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierReconciliation", "CausalFrontierReconciliationItem", "reconcile_causal_frontier"]
