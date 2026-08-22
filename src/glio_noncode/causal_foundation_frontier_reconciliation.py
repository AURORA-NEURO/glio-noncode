"""Expected-versus-observed reconciliation for causal foundation rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture
from .causal_foundation_frontier_policy import CausalFoundationFrontierPolicy, CausalFoundationFrontierPolicyDecision
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierReconciliationItem:
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
        values: list[str] = []
        if not self.state_match:
            values.append("state")
        if not self.issue_match:
            values.append("issue_codes")
        return tuple(values)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "expected_state": self.expected_state, "observed_state": self.observed_state, "expected_issue_codes": self.expected_issue_codes, "observed_issue_codes": self.observed_issue_codes, "state_match": self.state_match, "issue_match": self.issue_match, "policy_decision": self.policy_decision, "policy_rule_id": self.policy_rule_id, "accepted": self.accepted, "detail": self.detail, "mismatch_kinds": self.mismatch_kinds}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierReconciliation:
    fixture_id: str
    items: tuple[CausalFoundationFrontierReconciliationItem, ...]
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
    def review_count(self) -> int:
        return sum(item.policy_decision in {"review", "abstain"} for item in self.items)

    @property
    def quarantine_count(self) -> int:
        return sum(item.policy_decision == "quarantine" for item in self.items)

    def for_record(self, record_id: str) -> CausalFoundationFrontierReconciliationItem:
        return next(item for item in self.items if item.record_id == record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "items": [item.to_dict() for item in self.items], "state_match_count": self.state_match_count, "issue_match_count": self.issue_match_count, "reconciled": self.reconciled, "mismatch_record_ids": self.mismatch_record_ids, "accepted_count": self.accepted_count, "review_count": self.review_count, "quarantine_count": self.quarantine_count}
        if include_address:
            value["content_address"] = self.content_address
        return value


def reconcile_causal_foundation_frontier(
    fixture: CausalFoundationFrontierFixture,
    evaluation: CausalFoundationFrontierEvaluation,
    decisions: tuple[CausalFoundationFrontierPolicyDecision, ...] | None = None,
    policy: CausalFoundationFrontierPolicy | None = None,
) -> CausalFoundationFrontierReconciliation:
    active_policy = policy or __import__("glio_noncode.causal_foundation_frontier_policy", fromlist=["default_causal_foundation_frontier_policy"]).default_causal_foundation_frontier_policy()
    policy_values = decisions or active_policy.decide(evaluation)
    decision_map = {item.record_id: item for item in policy_values}
    items: list[CausalFoundationFrontierReconciliationItem] = []
    for row in evaluation.rows:
        decision = decision_map[row.record_id]
        accepted = row.state_match and row.issue_match and decision.decision.value != "quarantine"
        detail = "expected and observed state plus issue floor match" if accepted else "reconciliation requires review of state, issue floor, or policy disposition"
        items.append(CausalFoundationFrontierReconciliationItem(row.record_id, row.expected_state, row.observed_state, row.expected_issue_codes, row.observed_issue_codes, row.state_match, row.issue_match, decision.decision.value, decision.rule_id, accepted, detail))
    values = tuple(items)
    mismatches = tuple(item.record_id for item in values if not item.state_match or not item.issue_match)
    return CausalFoundationFrontierReconciliation(fixture.fixture_id, values, sum(item.state_match for item in values), sum(item.issue_match for item in values), bool(values) and not mismatches, mismatches)


__all__ = ["CausalFoundationFrontierReconciliation", "CausalFoundationFrontierReconciliationItem", "reconcile_causal_foundation_frontier"]
