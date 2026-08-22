"""Policy decisions that keep causal evidence bounded and reviewable."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_frontier_contracts import (
    CausalFrontierContractRegistry,
    default_causal_frontier_contracts,
)
from .causal_frontier_fixture_eval import CausalFrontierEvaluation
from .causal_frontier_public_data import CausalFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


class CausalFrontierDecision(StrEnum):
    ALLOW_REVIEW = "allow_review"
    ALLOW_PUBLICATION = "allow_publication"
    REQUIRE_REVIEW = "require_review"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class CausalFrontierPolicyRule:
    rule_id: str
    operation: CausalFrontierOperation
    decision: CausalFrontierDecision
    condition: str
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.rule_id, "rule_id")
        require_non_empty(self.condition, "condition")
        require_non_empty(self.rationale, "rationale")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierPolicyDecision:
    operation: CausalFrontierOperation
    decision: CausalFrontierDecision
    rule_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    reason: str
    content_address: str

    @property
    def publishable(self) -> bool:
        return self.decision is CausalFrontierDecision.ALLOW_PUBLICATION

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"publishable": self.publishable}


@dataclass(frozen=True, slots=True)
class CausalFrontierPolicy:
    policy_id: str
    version: str
    boundary: str
    rules: tuple[CausalFrontierPolicyRule, ...]
    contract_address: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.policy_id, "policy_id")
        require_non_empty(self.version, "version")
        require_non_empty(self.boundary, "boundary")

    def rule_map(self) -> dict[str, CausalFrontierPolicyRule]:
        return {item.rule_id: item for item in self.rules}

    def decide(self, evaluation: CausalFrontierEvaluation) -> tuple[CausalFrontierPolicyDecision, ...]:
        decisions: list[CausalFrontierPolicyDecision] = []
        for operation in CausalFrontierOperation:
            execution = next((item for item in evaluation.executions if item.operation is operation and item.accepted), None)
            issue_codes = tuple(sorted({code for item in evaluation.executions if item.operation is operation and item.role.value == "positive" for code in item.issue_codes}))
            if execution and operation is CausalFrontierOperation.DOSSIER_PUBLICATION and not issue_codes:
                decision = CausalFrontierDecision.ALLOW_PUBLICATION
                reason = "published dossier has complete bounded inputs and no operation issues"
                rule_ids = ("allow-published-dossier",)
            elif execution and not issue_codes:
                decision = CausalFrontierDecision.ALLOW_REVIEW
                reason = "supported aggregate result may enter review with no issue codes"
                rule_ids = ("allow-supported-review",)
            elif any(code.startswith("invalid_") or code.startswith("empty_") for code in issue_codes):
                decision = CausalFrontierDecision.BLOCK
                reason = "invalid or empty input cannot enter a release bundle"
                rule_ids = ("block-invalid-input",)
            else:
                decision = CausalFrontierDecision.REQUIRE_REVIEW
                reason = "bounded issue codes require human review before release"
                rule_ids = ("review-issue-bearing-output",)
            body = {
                "operation": operation,
                "decision": decision,
                "rule_ids": rule_ids,
                "issue_codes": issue_codes,
                "reason": reason,
            }
            decisions.append(CausalFrontierPolicyDecision(**body, content_address=content_hash(body)))
        return tuple(decisions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_causal_frontier_policy(
    contracts: CausalFrontierContractRegistry | None = None,
) -> CausalFrontierPolicy:
    contracts = contracts or default_causal_frontier_contracts()
    raw_rules = (
        ("allow-published-dossier", CausalFrontierOperation.DOSSIER_PUBLICATION, CausalFrontierDecision.ALLOW_PUBLICATION, "published operation has complete fields", "publication is a manifest receipt, not a claim"),
        ("allow-supported-review", CausalFrontierOperation.POSTERIOR_DECOMPOSITION, CausalFrontierDecision.ALLOW_REVIEW, "supported operation has bounded components", "supported aggregate output remains reviewable"),
        ("review-issue-bearing-output", CausalFrontierOperation.SELECTIVE_PREDICTION, CausalFrontierDecision.REQUIRE_REVIEW, "issue codes are present", "uncertainty and abstention remain visible"),
        ("block-invalid-input", CausalFrontierOperation.DRIVER_POSTERIOR, CausalFrontierDecision.BLOCK, "input is empty or invalid", "invalid inputs do not cross the release boundary"),
    )
    rules = tuple(
        CausalFrontierPolicyRule(*row, content_hash(row)) for row in raw_rules
    )
    body = {
        "policy_id": "causal-frontier-release-policy",
        "version": "2026.08.d11.v1",
        "boundary": "public_aggregate_non_patient",
        "rules": rules,
        "contract_address": contracts.content_address,
    }
    return CausalFrontierPolicy(**body, content_address=content_hash(body))


__all__ = [
    "CausalFrontierDecision",
    "CausalFrontierPolicy",
    "CausalFrontierPolicyDecision",
    "CausalFrontierPolicyRule",
    "default_causal_frontier_policy",
]
