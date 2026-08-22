"""Research-use policy for Domain 12 cohort convergence receipts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cohort_frontier_contracts import (
    CohortFrontierContractRegistry,
    default_cohort_frontier_contracts,
)
from .cohort_frontier_fixture_eval import CohortFrontierEvaluation
from .cohort_frontier_public_data import CohortFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


class CohortFrontierDecision(StrEnum):
    ALLOW_REVIEW = "allow_review"
    ALLOW_PUBLICATION = "allow_publication"
    REQUIRE_REVIEW = "require_review"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class CohortFrontierPolicyRule:
    rule_id: str
    operation: CohortFrontierOperation
    decision: CohortFrontierDecision
    condition: str
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "condition", "rationale", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierPolicyDecision:
    operation: CohortFrontierOperation
    decision: CohortFrontierDecision
    issue_codes: tuple[str, ...]
    rule_ids: tuple[str, ...]
    reason: str
    content_address: str

    @property
    def publishable(self) -> bool:
        return self.decision in {CohortFrontierDecision.ALLOW_REVIEW, CohortFrontierDecision.ALLOW_PUBLICATION}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"publishable": self.publishable}


@dataclass(frozen=True, slots=True)
class CohortFrontierPolicy:
    policy_id: str
    version: str
    boundary: str
    rules: tuple[CohortFrontierPolicyRule, ...]
    contract_address: str
    content_address: str

    def decide(self, evaluation: CohortFrontierEvaluation) -> tuple[CohortFrontierPolicyDecision, ...]:
        decisions: list[CohortFrontierPolicyDecision] = []
        for operation in CohortFrontierOperation:
            positive = next(item for item in evaluation.executions if item.operation is operation and item.role.value == "positive")
            issues = positive.issue_codes
            if operation is CohortFrontierOperation.COHORT_DISCOVERY and positive.accepted and not issues:
                decision, rule, reason = CohortFrontierDecision.ALLOW_PUBLICATION, "allow-published-discovery", "aggregate discovery manifest is publishable"
            elif positive.accepted and not issues:
                decision, rule, reason = CohortFrontierDecision.ALLOW_REVIEW, "allow-supported-cohort-review", "supported aggregate cohort summary may enter review"
            elif any(code.startswith("invalid_") or code.startswith("empty_") for code in issues):
                decision, rule, reason = CohortFrontierDecision.BLOCK, "block-invalid-cohort-input", "invalid or empty positive input is blocked"
            else:
                decision, rule, reason = CohortFrontierDecision.REQUIRE_REVIEW, "review-cohort-issues", "issue-bearing cohort output requires review"
            body = {"operation": operation, "decision": decision, "issue_codes": issues, "rule_ids": (rule,), "reason": reason}
            decisions.append(CohortFrontierPolicyDecision(**body, content_address=content_hash(body)))
        return tuple(decisions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_frontier_policy(contracts: CohortFrontierContractRegistry | None = None) -> CohortFrontierPolicy:
    contracts = contracts or default_cohort_frontier_contracts()
    rows = (("allow-published-discovery", CohortFrontierOperation.COHORT_DISCOVERY, CohortFrontierDecision.ALLOW_PUBLICATION, "valid aggregate discovery manifest", "publication is a research manifest"), ("allow-supported-cohort-review", CohortFrontierOperation.SUBGROUP_FAIRNESS, CohortFrontierDecision.ALLOW_REVIEW, "bounded cohort result has no positive issue", "review retains cohort limitations"), ("review-cohort-issues", CohortFrontierOperation.TRANSPORTABILITY, CohortFrontierDecision.REQUIRE_REVIEW, "issue codes are present", "shift and overlap remain visible"), ("block-invalid-cohort-input", CohortFrontierOperation.FEDERATED_SUMMARY, CohortFrontierDecision.BLOCK, "positive input is invalid or empty", "invalid aggregate summaries do not cross release"))
    rules = tuple(CohortFrontierPolicyRule(*row, content_hash(row)) for row in rows)
    body = {"policy_id": "cohort-frontier-release-policy", "version": "2026.08.d12.v1", "boundary": "public_aggregate_non_patient", "rules": rules, "contract_address": contracts.content_address}
    return CohortFrontierPolicy(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierDecision", "CohortFrontierPolicy", "CohortFrontierPolicyDecision", "CohortFrontierPolicyRule", "default_cohort_frontier_policy"]
