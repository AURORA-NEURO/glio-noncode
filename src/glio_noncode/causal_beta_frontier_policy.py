"""Bounded dispositions for C05-C08 mediator and allele outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_public_data import CausalBetaFrontierOperation, CausalBetaFrontierRole
from .serialization import content_hash, jsonable, require_non_empty


class CausalBetaFrontierDecision(StrEnum):
    RETAIN = "retain"
    REVIEW = "review"
    ABSTAIN = "abstain"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierPolicyRule:
    rule_id: str
    operation: CausalBetaFrontierOperation
    role: CausalBetaFrontierRole | None
    state: str | None
    decision: CausalBetaFrontierDecision
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.rule_id, "rule_id")
        require_non_empty(self.rationale, "rationale")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def matches(self, operation: str, role: str, state: str) -> bool:
        return self.operation.value == operation and (self.role is None or self.role.value == role) and (self.state is None or self.state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rule_id": self.rule_id, "operation": self.operation, "role": self.role, "state": self.state, "decision": self.decision, "rationale": self.rationale}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierPolicyDecision:
    record_id: str
    operation: str
    role: str
    state: str
    decision: CausalBetaFrontierDecision
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
        return self.decision in {CausalBetaFrontierDecision.REVIEW, CausalBetaFrontierDecision.ABSTAIN}

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "role": self.role, "state": self.state, "decision": self.decision, "rule_id": self.rule_id, "issue_codes": self.issue_codes, "reason": self.reason, "publishable": self.publishable, "requires_human_review": self.requires_human_review}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierPolicy:
    policy_id: str
    version: str
    boundary: str
    rules: tuple[CausalBetaFrontierPolicyRule, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("policy_id", "version", "boundary"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def decide_row(self, row: Any) -> CausalBetaFrontierPolicyDecision:
        rule = next((item for item in self.rules if item.matches(row.operation, row.role, row.observed_state)), None)
        if rule is None:
            decision, rule_id, reason = CausalBetaFrontierDecision.REVIEW, "default-review", "unmatched output remains in review"
        else:
            decision, rule_id, reason = rule.decision, rule.rule_id, rule.rationale
        publishable = decision is CausalBetaFrontierDecision.RETAIN and row.role == CausalBetaFrontierRole.POSITIVE.value and row.observed_state == "supported"
        return CausalBetaFrontierPolicyDecision(row.record_id, row.operation, row.role, row.observed_state, decision, rule_id, tuple(row.observed_issue_codes), reason, publishable)

    def decide(self, evaluation: CausalBetaFrontierEvaluation) -> tuple[CausalBetaFrontierPolicyDecision, ...]:
        return tuple(self.decide_row(row) for row in evaluation.rows)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"policy_id": self.policy_id, "version": self.version, "boundary": self.boundary, "rules": [item.to_dict() for item in self.rules]}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_causal_beta_frontier_policy() -> CausalBetaFrontierPolicy:
    rules = (
        CausalBetaFrontierPolicyRule("retain-sequence-positive", CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, CausalBetaFrontierRole.POSITIVE, "supported", CausalBetaFrontierDecision.RETAIN, "independent sequence paths may enter aggregate review"),
        CausalBetaFrontierPolicyRule("retain-element-positive", CausalBetaFrontierOperation.ELEMENT_TO_GENE, CausalBetaFrontierRole.POSITIVE, "supported", CausalBetaFrontierDecision.RETAIN, "independent element paths may enter aggregate review"),
        CausalBetaFrontierPolicyRule("retain-gene-positive", CausalBetaFrontierOperation.GENE_TO_STATE, CausalBetaFrontierRole.POSITIVE, "supported", CausalBetaFrontierDecision.RETAIN, "independent state paths may enter aggregate review"),
        CausalBetaFrontierPolicyRule("retain-allele-positive", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, CausalBetaFrontierRole.POSITIVE, "supported", CausalBetaFrontierDecision.RETAIN, "descriptive allele delta may enter aggregate review"),
        CausalBetaFrontierPolicyRule("review-minimum-sources", CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, None, "partial", CausalBetaFrontierDecision.REVIEW, "independent-source minimum is not met"),
        CausalBetaFrontierPolicyRule("review-element-sources", CausalBetaFrontierOperation.ELEMENT_TO_GENE, None, "partial", CausalBetaFrontierDecision.REVIEW, "independent-source minimum is not met"),
        CausalBetaFrontierPolicyRule("review-gene-sources", CausalBetaFrontierOperation.GENE_TO_STATE, None, "partial", CausalBetaFrontierDecision.REVIEW, "independent-source minimum is not met"),
        CausalBetaFrontierPolicyRule("abstain-allele-missing", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, None, "partial", CausalBetaFrontierDecision.ABSTAIN, "one allele is missing and no delta can be formed"),
        CausalBetaFrontierPolicyRule("review-allele-ambiguous", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, None, "ambiguous", CausalBetaFrontierDecision.REVIEW, "replicate spread exceeds the declared tolerance"),
        CausalBetaFrontierPolicyRule("quarantine-sequence-contradiction", CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, None, "contradictory", CausalBetaFrontierDecision.QUARANTINE, "against-direction evidence remains visible and blocks retention"),
        CausalBetaFrontierPolicyRule("quarantine-element-contradiction", CausalBetaFrontierOperation.ELEMENT_TO_GENE, None, "contradictory", CausalBetaFrontierDecision.QUARANTINE, "directional disagreement blocks retention"),
        CausalBetaFrontierPolicyRule("quarantine-gene-contradiction", CausalBetaFrontierOperation.GENE_TO_STATE, None, "contradictory", CausalBetaFrontierDecision.QUARANTINE, "negative-control conflict blocks retention"),
        CausalBetaFrontierPolicyRule("quarantine-foreign-sequence", CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, None, "out_of_domain", CausalBetaFrontierDecision.QUARANTINE, "foreign context is not transported"),
        CausalBetaFrontierPolicyRule("quarantine-foreign-element", CausalBetaFrontierOperation.ELEMENT_TO_GENE, None, "out_of_domain", CausalBetaFrontierDecision.QUARANTINE, "foreign context is not transported"),
        CausalBetaFrontierPolicyRule("quarantine-foreign-gene", CausalBetaFrontierOperation.GENE_TO_STATE, None, "out_of_domain", CausalBetaFrontierDecision.QUARANTINE, "foreign state context is not transported"),
        CausalBetaFrontierPolicyRule("quarantine-foreign-allele", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, None, "out_of_domain", CausalBetaFrontierDecision.QUARANTINE, "foreign allele context is not transported"),
    )
    return CausalBetaFrontierPolicy("causal-beta-frontier-policy", "2026.08.d11-c05-c08.v1", "public_aggregate_non_patient", rules)


__all__ = ["CausalBetaFrontierDecision", "CausalBetaFrontierPolicy", "CausalBetaFrontierPolicyDecision", "CausalBetaFrontierPolicyRule", "default_causal_beta_frontier_policy"]
