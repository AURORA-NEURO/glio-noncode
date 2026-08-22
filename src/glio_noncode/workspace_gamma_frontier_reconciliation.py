"""Reconcile fixture expectations, observed executions, and policy evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation
from .workspace_gamma_frontier_policy import GammaFrontierPolicyDecision
from .workspace_gamma_frontier_public_data import GammaFrontierFixture


@dataclass(frozen=True, slots=True)
class GammaFrontierReconciliationItem:
    """One row-level reconciliation result."""

    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    policy_decision: str
    state_match: bool
    issue_match: bool
    reconciled: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierReconciliation:
    """Complete expected-versus-observed reconciliation."""

    fixture_id: str
    items: tuple[GammaFrontierReconciliationItem, ...]
    accepted: bool
    content_address: str

    @property
    def mismatches(self) -> tuple[GammaFrontierReconciliationItem, ...]:
        return tuple(item for item in self.items if not item.reconciled)

    def by_record(self, record_id: str) -> GammaFrontierReconciliationItem:
        return next(item for item in self.items if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"mismatch_count": len(self.mismatches)}


def reconcile_gamma_frontier(
    fixture: GammaFrontierFixture,
    evaluation: GammaFrontierEvaluation,
    decisions: tuple[GammaFrontierPolicyDecision, ...] | None = None,
) -> GammaFrontierReconciliation:
    """Compare every expected state and issue set with its execution receipt."""

    decision_map = {item.record_id: item for item in decisions or ()}
    items: list[GammaFrontierReconciliationItem] = []
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        expected = tuple(sorted(record.expected_issue_codes))
        observed = tuple(sorted(execution.issue_codes))
        state_match = record.expected_state == execution.state
        issue_match = expected == observed
        policy = decision_map.get(record.record_id)
        policy_value = "unrouted" if policy is None else policy.decision.value
        detail = (
            "state and issue evidence agree"
            if state_match and issue_match
            else "expected and observed evidence differ"
        )
        body = {
            "record_id": record.record_id,
            "expected_state": record.expected_state,
            "observed_state": execution.state,
            "expected_issue_codes": expected,
            "observed_issue_codes": observed,
            "policy_decision": policy_value,
            "state_match": state_match,
            "issue_match": issue_match,
            "reconciled": state_match and issue_match,
            "detail": detail,
        }
        items.append(GammaFrontierReconciliationItem(**body, content_address=content_hash(body)))
    body = {
        "fixture_id": fixture.fixture_id,
        "items": tuple(items),
        "accepted": all(item.reconciled for item in items),
    }
    return GammaFrontierReconciliation(**body, content_address=content_hash(body))


__all__ = [
    "GammaFrontierReconciliation",
    "GammaFrontierReconciliationItem",
    "reconcile_gamma_frontier",
]
