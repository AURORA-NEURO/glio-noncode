"""Research-use policy decisions for validation planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_contracts import ValidationFrontierContractRegistry
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_public_data import ValidationFrontierOperation, ValidationFrontierRole


class ValidationFrontierDecision(StrEnum):
    ALLOW_PLANNING_REVIEW = "allow_planning_review"
    ALLOW_ROUTE_REVIEW = "allow_route_review"
    BLOCK_RELEASE = "block_release"


@dataclass(frozen=True, slots=True)
class ValidationFrontierPolicyRule:
    operation: ValidationFrontierOperation
    decision: ValidationFrontierDecision
    required_state: str
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierPolicyDecision:
    operation: ValidationFrontierOperation
    decision: ValidationFrontierDecision
    publishable: bool
    record_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierPolicy:
    policy_id: str
    rules: tuple[ValidationFrontierPolicyRule, ...]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    content_address: str

    def by_operation(self, operation: ValidationFrontierOperation) -> ValidationFrontierPolicyRule:
        return next(item for item in self.rules if item.operation is operation)

    def decide(self, evaluation: ValidationFrontierEvaluation) -> tuple[ValidationFrontierPolicyDecision, ...]:
        decisions = []
        for operation in ValidationFrontierOperation:
            positive = tuple(item for item in evaluation.executions if item.operation is operation and item.role is ValidationFrontierRole.POSITIVE)
            rule = self.by_operation(operation)
            publishable = bool(positive and positive[0].accepted)
            body = {"operation": operation, "decision": rule.decision if publishable else ValidationFrontierDecision.BLOCK_RELEASE, "publishable": publishable, "record_ids": tuple(item.record_id for item in positive), "issue_codes": positive[0].issue_codes if positive else ("positive_record_missing",)}
            decisions.append(ValidationFrontierPolicyDecision(**body, content_address=content_hash(body)))
        return tuple(decisions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_validation_frontier_policy(contracts: ValidationFrontierContractRegistry) -> ValidationFrontierPolicy:
    rules = tuple(ValidationFrontierPolicyRule(operation, ValidationFrontierDecision.ALLOW_ROUTE_REVIEW if operation is ValidationFrontierOperation.ASSAY_ELIGIBILITY else ValidationFrontierDecision.ALLOW_PLANNING_REVIEW, "partial" if operation is ValidationFrontierOperation.EVIDENCE_GAP else "ready_for_review", "bounded planning output remains a review artifact", content_hash({"operation": operation, "decision": "allow"})) for operation in ValidationFrontierOperation)
    body = {"policy_id": "validation-frontier-policy", "rules": rules, "allowed_uses": ("assay planning review", "method development", "reproducibility testing", "research triage"), "excluded_uses": ("patient care", "diagnosis", "prognosis", "treatment selection", "individual risk", "clinical validation claims")}
    return ValidationFrontierPolicy(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierDecision", "ValidationFrontierPolicy", "ValidationFrontierPolicyDecision", "ValidationFrontierPolicyRule", "default_validation_frontier_policy"]
