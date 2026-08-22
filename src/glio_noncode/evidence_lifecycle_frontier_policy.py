"""Research-use policy decisions for the Domain 14 lifecycle frontier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .evidence_lifecycle_frontier_public_data import (
    EvidenceLifecycleOperation,
    EvidenceLifecycleRole,
)
from .serialization import content_hash, jsonable, require_non_empty


class EvidenceLifecycleDecision(StrEnum):
    ALLOW_REVIEW = "allow_review"
    ALLOW_REPLAY = "allow_replay"
    BLOCK_RELEASE = "block_release"


@dataclass(frozen=True, slots=True)
class EvidenceLifecyclePolicyRule:
    operation: EvidenceLifecycleOperation
    decision: EvidenceLifecycleDecision
    required_state: str
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecyclePolicyDecision:
    operation: EvidenceLifecycleOperation
    decision: EvidenceLifecycleDecision
    publishable: bool
    record_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecyclePolicy:
    policy_id: str
    rules: tuple[EvidenceLifecyclePolicyRule, ...]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    content_address: str

    def by_operation(self, operation: EvidenceLifecycleOperation) -> EvidenceLifecyclePolicyRule:
        return next(item for item in self.rules if item.operation is operation)

    def decide(self, evaluation: EvidenceLifecycleEvaluation) -> tuple[EvidenceLifecyclePolicyDecision, ...]:
        decisions: list[EvidenceLifecyclePolicyDecision] = []
        for operation in EvidenceLifecycleOperation:
            positive = tuple(item for item in evaluation.executions if item.operation is operation and item.role is EvidenceLifecycleRole.POSITIVE)
            rule = self.by_operation(operation)
            publishable = bool(positive and positive[0].accepted)
            body = {"operation": operation, "decision": rule.decision if publishable else EvidenceLifecycleDecision.BLOCK_RELEASE, "publishable": publishable, "record_ids": tuple(item.record_id for item in positive), "issue_codes": positive[0].issue_codes if positive else ("positive_record_missing",)}
            decisions.append(EvidenceLifecyclePolicyDecision(**body, content_address=content_hash(body)))
        return tuple(decisions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_evidence_lifecycle_policy() -> EvidenceLifecyclePolicy:
    rules = tuple(EvidenceLifecyclePolicyRule(operation, EvidenceLifecycleDecision.ALLOW_REPLAY if operation is EvidenceLifecycleOperation.GRAPH_CONSTRUCTION else EvidenceLifecycleDecision.ALLOW_REVIEW, "supported" if operation is not EvidenceLifecycleOperation.DISAGREEMENT_TRACKING else "contradictory", "public aggregate lifecycle output remains review-scoped", content_hash({"operation": operation, "decision": "allow"})) for operation in EvidenceLifecycleOperation)
    body = {"policy_id": "evidence-lifecycle-frontier-policy", "rules": rules, "allowed_uses": ("provenance review", "citation reconciliation", "research triage", "reproducibility testing"), "excluded_uses": ("patient care", "diagnosis", "prognosis", "treatment selection", "individual risk", "clinical validation claims")}
    require_non_empty(body["policy_id"], "policy_id")
    return EvidenceLifecyclePolicy(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleDecision", "EvidenceLifecyclePolicy", "EvidenceLifecyclePolicyDecision", "EvidenceLifecyclePolicyRule", "default_evidence_lifecycle_policy"]
