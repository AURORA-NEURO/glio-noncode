"""Bounded publication policy for Domain 11 C01-C04 outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_public_data import CausalFoundationFrontierOperation, CausalFoundationFrontierRole
from .serialization import content_hash, jsonable, require_non_empty


class CausalFoundationFrontierDecision(StrEnum):
    RETAIN = "retain"
    REVIEW = "review"
    ABSTAIN = "abstain"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierPolicyRule:
    rule_id: str
    operation: CausalFoundationFrontierOperation
    role: CausalFoundationFrontierRole | None
    state: str | None
    decision: CausalFoundationFrontierDecision
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.rule_id, "rule_id")
        require_non_empty(self.rationale, "rationale")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def matches(self, operation: str, role: str, state: str) -> bool:
        return (
            self.operation.value == operation
            and (self.role is None or self.role.value == role)
            and (self.state is None or self.state == state)
        )

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rule_id": self.rule_id, "operation": self.operation, "role": self.role, "state": self.state, "decision": self.decision, "rationale": self.rationale}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierPolicyDecision:
    record_id: str
    operation: str
    role: str
    state: str
    decision: CausalFoundationFrontierDecision
    rule_id: str
    issue_codes: tuple[str, ...]
    reason: str
    publishable: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def requires_human_review(self) -> bool:
        return self.decision in {CausalFoundationFrontierDecision.REVIEW, CausalFoundationFrontierDecision.ABSTAIN}

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "role": self.role, "state": self.state, "decision": self.decision, "rule_id": self.rule_id, "issue_codes": self.issue_codes, "reason": self.reason, "publishable": self.publishable, "requires_human_review": self.requires_human_review}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierPolicy:
    policy_id: str
    version: str
    boundary: str
    rules: tuple[CausalFoundationFrontierPolicyRule, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("policy_id", "version", "boundary"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def rule_map(self) -> dict[str, CausalFoundationFrontierPolicyRule]:
        return {item.rule_id: item for item in self.rules}

    def decide_row(self, row: Any) -> CausalFoundationFrontierPolicyDecision:
        state = str(row.observed_state)
        role = str(row.role)
        operation = str(row.operation)
        rule = next((item for item in self.rules if item.matches(operation, role, state)), None)
        if rule is None:
            decision = CausalFoundationFrontierDecision.REVIEW
            rule_id = "default-review"
            reason = "unmatched state remains in review until a bounded rule is declared"
        else:
            decision = rule.decision
            rule_id = rule.rule_id
            reason = rule.rationale
        publishable = decision is CausalFoundationFrontierDecision.RETAIN and role == CausalFoundationFrontierRole.POSITIVE.value and state == "supported"
        return CausalFoundationFrontierPolicyDecision(row.record_id, operation, role, state, decision, rule_id, tuple(row.observed_issue_codes), reason, publishable)

    def decide(self, evaluation: CausalFoundationFrontierEvaluation) -> tuple[CausalFoundationFrontierPolicyDecision, ...]:
        return tuple(self.decide_row(row) for row in evaluation.rows)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"policy_id": self.policy_id, "version": self.version, "boundary": self.boundary, "rules": [item.to_dict() for item in self.rules]}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_causal_foundation_frontier_policy() -> CausalFoundationFrontierPolicy:
    rules = (
        CausalFoundationFrontierPolicyRule("retain-supported-positive", CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, CausalFoundationFrontierRole.POSITIVE, "supported", CausalFoundationFrontierDecision.RETAIN, "supported positive aggregate output may proceed to review artifacts"),
        CausalFoundationFrontierPolicyRule("retain-graph-positive", CausalFoundationFrontierOperation.FACTOR_GRAPH, CausalFoundationFrontierRole.POSITIVE, "supported", CausalFoundationFrontierDecision.RETAIN, "supported factor graph may proceed with lineage attached"),
        CausalFoundationFrontierPolicyRule("retain-prior-positive", CausalFoundationFrontierOperation.CONTEXT_PRIOR, CausalFoundationFrontierRole.POSITIVE, "supported", CausalFoundationFrontierDecision.RETAIN, "bounded prior proxy may proceed with calibration limitation"),
        CausalFoundationFrontierPolicyRule("retain-likelihood-positive", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, CausalFoundationFrontierRole.POSITIVE, "supported", CausalFoundationFrontierDecision.RETAIN, "dependent-channel likelihood proxy may proceed as descriptive evidence"),
        CausalFoundationFrontierPolicyRule("review-partial", CausalFoundationFrontierOperation.FACTOR_GRAPH, None, "partial", CausalFoundationFrontierDecision.REVIEW, "partial graph requires lineage review"),
        CausalFoundationFrontierPolicyRule("review-partial-measurement", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, None, "partial", CausalFoundationFrontierDecision.REVIEW, "single channel group is not sufficient for a complete likelihood proxy"),
        CausalFoundationFrontierPolicyRule("abstain-missing", CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, None, "abstained", CausalFoundationFrontierDecision.ABSTAIN, "missing prior evidence prevents completion"),
        CausalFoundationFrontierPolicyRule("abstain-prior-missing", CausalFoundationFrontierOperation.CONTEXT_PRIOR, None, "abstained", CausalFoundationFrontierDecision.ABSTAIN, "missing context feature prevents prior evaluation"),
        CausalFoundationFrontierPolicyRule("quarantine-contradictory", CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, None, "contradictory", CausalFoundationFrontierDecision.QUARANTINE, "contradictory factors stay visible but cannot be retained"),
        CausalFoundationFrontierPolicyRule("quarantine-factor-contradiction", CausalFoundationFrontierOperation.FACTOR_GRAPH, None, "contradictory", CausalFoundationFrontierDecision.QUARANTINE, "contradictory graph edges require quarantine"),
        CausalFoundationFrontierPolicyRule("quarantine-measurement-contradiction", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, None, "contradictory", CausalFoundationFrontierDecision.QUARANTINE, "contradictory measurement states cannot be averaged away"),
        CausalFoundationFrontierPolicyRule("quarantine-out-of-domain", CausalFoundationFrontierOperation.CONTEXT_PRIOR, None, "out_of_domain", CausalFoundationFrontierDecision.QUARANTINE, "context or feature support mismatch is quarantined"),
        CausalFoundationFrontierPolicyRule("quarantine-foreign-hypothesis", CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, None, "out_of_domain", CausalFoundationFrontierDecision.QUARANTINE, "foreign hypothesis context is not transported"),
        CausalFoundationFrontierPolicyRule("quarantine-foreign-graph", CausalFoundationFrontierOperation.FACTOR_GRAPH, None, "out_of_domain", CausalFoundationFrontierDecision.QUARANTINE, "foreign graph context is not transported"),
        CausalFoundationFrontierPolicyRule("quarantine-foreign-likelihood", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, None, "out_of_domain", CausalFoundationFrontierDecision.QUARANTINE, "foreign measurement context is not transported"),
    )
    return CausalFoundationFrontierPolicy("causal-foundation-frontier-policy", "2026.08.d11-c01-c04.v1", "public_aggregate_non_patient", rules)


__all__ = ["CausalFoundationFrontierDecision", "CausalFoundationFrontierPolicy", "CausalFoundationFrontierPolicyDecision", "CausalFoundationFrontierPolicyRule", "default_causal_foundation_frontier_policy"]
