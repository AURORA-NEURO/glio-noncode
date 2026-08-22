"""Expected-versus-observed reconciliation for projection rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_policy import BetaFrontierPolicy, BetaFrontierPolicyDecision
from .workspace_beta_frontier_public_data import BetaFrontierFixture, BetaFrontierRole


@dataclass(frozen=True, slots=True)
class BetaFrontierReconciliationItem:
    """One expected/observed row comparison."""

    record_id: str
    role: BetaFrontierRole
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    policy_decision: str
    content_address: str

    @property
    def reconciled(self) -> bool:
        return self.state_match and self.issue_match

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"reconciled": self.reconciled}


@dataclass(frozen=True, slots=True)
class BetaFrontierReconciliation:
    """Aggregate reconciliation report used by release gates."""

    fixture_id: str
    items: tuple[BetaFrontierReconciliationItem, ...]
    reconciled: bool
    mismatch_ids: tuple[str, ...]
    ready_count: int
    held_count: int
    content_address: str

    def by_record(self, record_id: str) -> BetaFrontierReconciliationItem:
        return next(item for item in self.items if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_beta_frontier(
    fixture: BetaFrontierFixture,
    evaluation: BetaFrontierEvaluation,
    policy: BetaFrontierPolicy,
) -> BetaFrontierReconciliation:
    """Compare each result to its declared fixture contract."""

    execution_map = evaluation.execution_map()
    decisions = {item.record_id: item for item in policy.decide(evaluation)}
    items: list[BetaFrontierReconciliationItem] = []
    for record in fixture.records:
        execution = execution_map[record.record_id]
        decision: BetaFrontierPolicyDecision = decisions[record.record_id]
        body = {
            "record_id": record.record_id,
            "role": record.role,
            "expected_state": record.expected_state,
            "observed_state": execution.state,
            "expected_issue_codes": tuple(sorted(record.expected_issue_codes)),
            "observed_issue_codes": tuple(sorted(execution.issue_codes)),
            "state_match": record.expected_state == execution.state,
            "issue_match": tuple(sorted(record.expected_issue_codes)) == tuple(sorted(execution.issue_codes)),
            "policy_decision": decision.decision.value,
        }
        items.append(BetaFrontierReconciliationItem(**body, content_address=content_hash(body)))
    mismatch = tuple(item.record_id for item in items if not item.reconciled)
    ready = sum(item.policy_decision == "ready" for item in items)
    held = sum(item.policy_decision == "hold" for item in items)
    body = {"fixture_id": fixture.fixture_id, "items": tuple(items), "reconciled": not mismatch, "mismatch_ids": mismatch, "ready_count": ready, "held_count": held}
    return BetaFrontierReconciliation(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierReconciliation", "BetaFrontierReconciliationItem", "reconcile_beta_frontier"]
