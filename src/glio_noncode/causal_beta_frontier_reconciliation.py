"""Expected-versus-observed reconciliation for beta frontier rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_policy import CausalBetaFrontierPolicy, CausalBetaFrontierPolicyDecision, default_causal_beta_frontier_policy
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    policy_decision: str
    policy_rule_id: str
    accepted: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def mismatch_kinds(self) -> tuple[str, ...]:
        return tuple(kind for kind, failed in (("state", not self.state_match), ("issue_codes", not self.issue_match)) if failed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "expected_state": self.expected_state, "observed_state": self.observed_state, "expected_issue_codes": self.expected_issue_codes, "observed_issue_codes": self.observed_issue_codes, "state_match": self.state_match, "issue_match": self.issue_match, "policy_decision": self.policy_decision, "policy_rule_id": self.policy_rule_id, "accepted": self.accepted, "detail": self.detail, "mismatch_kinds": self.mismatch_kinds}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReconciliation:
    fixture_id: str
    items: tuple[CausalBetaFrontierReconciliationItem, ...]
    state_match_count: int
    issue_match_count: int
    reconciled: bool
    mismatch_record_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def accepted_count(self) -> int:
        return sum(item.accepted for item in self.items)

    @property
    def blocked_count(self) -> int:
        return sum(item.policy_decision == "quarantine" for item in self.items)

    @property
    def review_count(self) -> int:
        return sum(item.policy_decision in {"review", "abstain"} for item in self.items)

    def for_record(self, record_id: str) -> CausalBetaFrontierReconciliationItem:
        return next(item for item in self.items if item.record_id == record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "items": [item.to_dict() for item in self.items], "state_match_count": self.state_match_count, "issue_match_count": self.issue_match_count, "reconciled": self.reconciled, "mismatch_record_ids": self.mismatch_record_ids, "accepted_count": self.accepted_count, "blocked_count": self.blocked_count, "review_count": self.review_count}
        if include_address:
            value["content_address"] = self.content_address
        return value


def reconcile_causal_beta_frontier(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, decisions: tuple[CausalBetaFrontierPolicyDecision, ...] | None = None, policy: CausalBetaFrontierPolicy | None = None) -> CausalBetaFrontierReconciliation:
    active = policy or default_causal_beta_frontier_policy()
    values = decisions or active.decide(evaluation)
    decision_map = {item.record_id: item for item in values}
    items = tuple(CausalBetaFrontierReconciliationItem(row.record_id, row.expected_state, row.observed_state, row.expected_issue_codes, row.observed_issue_codes, row.state_match, row.issue_match, decision_map[row.record_id].decision.value, decision_map[row.record_id].rule_id, row.state_match and row.issue_match and decision_map[row.record_id].decision.value != "quarantine", "expected and observed controls reconcile" if row.state_match and row.issue_match else "state or issue floor mismatch requires review") for row in evaluation.rows)
    mismatches = tuple(item.record_id for item in items if not item.state_match or not item.issue_match)
    return CausalBetaFrontierReconciliation(fixture.fixture_id, items, sum(item.state_match for item in items), sum(item.issue_match for item in items), bool(items) and not mismatches, mismatches)


__all__ = ["CausalBetaFrontierReconciliation", "CausalBetaFrontierReconciliationItem", "reconcile_causal_beta_frontier"]
