"""Deny-by-default publication policy for cohort foundation evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_contracts import CohortFoundationContractRegistry, default_cohort_foundation_frontier_contracts
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_public_data import CohortFoundationOperation, CohortFoundationRole


class CohortFoundationDisposition(StrEnum):
    ALLOW_DESCRIPTIVE = "allow_descriptive"
    REVIEW = "review"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class CohortFoundationPolicyDecision:
    record_id: str
    operation: CohortFoundationOperation
    role: CohortFoundationRole
    state: str
    disposition: CohortFoundationDisposition
    issue_codes: tuple[str, ...]
    permitted_fields: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationPolicy:
    policy_id: str
    version: str
    decisions: tuple[CohortFoundationPolicyDecision, ...]
    content_address: str

    def decision_for(self, record_id: str) -> CohortFoundationPolicyDecision:
        return next(item for item in self.decisions if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _permitted(operation: CohortFoundationOperation) -> tuple[str, ...]:
    common = ("record_id", "operation", "state", "source_ids", "context_key", "content_address")
    extras = {
        CohortFoundationOperation.COHORT_QUERY: ("variant_ids", "excluded_count", "excluded_reasons"),
        CohortFoundationOperation.BACKGROUND_RATE: ("observed_count", "callable_bases", "expected_count", "uncertainty"),
        CohortFoundationOperation.SEQUENCE_CONTROL: ("target_id", "candidate_count", "distance", "control_ids"),
        CohortFoundationOperation.CHROMATIN_CONTROL: ("target_id", "candidate_count", "distance", "control_ids"),
    }
    return common + extras[operation]


def default_cohort_foundation_frontier_policy(contracts: CohortFoundationContractRegistry | None = None) -> CohortFoundationPolicy:
    registry = contracts or default_cohort_foundation_frontier_contracts()
    decisions: list[CohortFoundationPolicyDecision] = []
    # The policy template is materialized for states and controls by the evaluator.
    for operation in CohortFoundationOperation:
        contract = registry.by_operation(operation)
        for state, disposition, rationale in (
            ("supported", CohortFoundationDisposition.ALLOW_DESCRIPTIVE, "exact-context aggregate output may be described"),
            ("partial", CohortFoundationDisposition.REVIEW, "selection or control coverage is incomplete"),
            ("absent", CohortFoundationDisposition.REVIEW, "absence is not a negative causal result"),
            ("abstained", CohortFoundationDisposition.REVIEW, "required denominator or input was unavailable"),
            ("out_of_domain", CohortFoundationDisposition.QUARANTINE, "foreign context cannot be transported"),
        ):
            record_id = f"template:{operation.value}:{state}"
            body = {"record_id": record_id, "operation": operation, "state": state, "disposition": disposition, "rationale": rationale}
            decisions.append(CohortFoundationPolicyDecision(record_id, operation, CohortFoundationRole.CONTROL, state, disposition, (), _permitted(operation), contract.prohibited_claims, rationale, content_hash(body)))
    body = {"policy_id": "cohort-foundation-frontier-policy", "version": "1.0.0", "decisions": decisions}
    return CohortFoundationPolicy(body["policy_id"], body["version"], tuple(decisions), content_hash(body))


def materialize_cohort_foundation_frontier_policy(evaluation: CohortFoundationEvaluation, contracts: CohortFoundationContractRegistry | None = None) -> CohortFoundationPolicy:
    registry = contracts or default_cohort_foundation_frontier_contracts()
    decisions = []
    for execution in evaluation.executions:
        contract = registry.by_operation(execution.operation)
        if execution.actual_state == "supported":
            disposition = CohortFoundationDisposition.ALLOW_DESCRIPTIVE
            rationale = "exact-context aggregate output may be described"
        elif execution.actual_state == "out_of_domain":
            disposition = CohortFoundationDisposition.QUARANTINE
            rationale = "foreign context cannot be transported"
        else:
            disposition = CohortFoundationDisposition.REVIEW
            rationale = "incomplete or absent evidence requires review"
        body = {"record_id": execution.record_id, "operation": execution.operation, "role": execution.role, "state": execution.actual_state, "disposition": disposition, "issues": execution.issues}
        decisions.append(CohortFoundationPolicyDecision(execution.record_id, execution.operation, execution.role, execution.actual_state, disposition, execution.issues, _permitted(execution.operation), contract.prohibited_claims, rationale, content_hash(body)))
    body = {"policy_id": "cohort-foundation-frontier-policy", "version": "1.0.0", "decisions": decisions}
    return CohortFoundationPolicy(body["policy_id"], body["version"], tuple(decisions), content_hash(body))


__all__ = ["CohortFoundationDisposition", "CohortFoundationPolicy", "CohortFoundationPolicyDecision", "default_cohort_foundation_frontier_policy", "materialize_cohort_foundation_frontier_policy"]
