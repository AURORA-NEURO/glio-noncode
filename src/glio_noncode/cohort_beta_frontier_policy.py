"""State-aware publication policy for aggregate recurrence and convergence results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cohort_beta import CohortBetaState
from .cohort_beta_frontier_contracts import CohortBetaFrontierContractRegistry
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .serialization import content_hash, jsonable


class CohortBetaFrontierDisposition(StrEnum):
    PUBLISH = "publish"
    REVIEW = "review"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierPolicyDecision:
    record_id: str
    operation: str
    state: CohortBetaState
    disposition: CohortBetaFrontierDisposition
    rationale: str
    prohibited_claims: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierPolicy:
    decisions: tuple[CohortBetaFrontierPolicyDecision, ...]
    publishable_count: int
    review_count: int
    quarantine_count: int
    content_address: str

    def for_record(self, record_id: str) -> CohortBetaFrontierPolicyDecision:
        return next(item for item in self.decisions if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def materialize_cohort_beta_frontier_policy(evaluation: CohortBetaFrontierEvaluation, contracts: CohortBetaFrontierContractRegistry) -> CohortBetaFrontierPolicy:
    decisions: list[CohortBetaFrontierPolicyDecision] = []
    for row in evaluation.rows:
        if row.observed_state is CohortBetaState.SUPPORTED and row.accepted:
            disposition = CohortBetaFrontierDisposition.PUBLISH
            rationale = "bounded descriptive result passed exact-context and fixture reconciliation"
        elif row.observed_state in {CohortBetaState.PARTIAL, CohortBetaState.AMBIGUOUS}:
            disposition = CohortBetaFrontierDisposition.REVIEW
            rationale = "result is incomplete or ambiguous and needs a declared comparator or adjudication"
        else:
            disposition = CohortBetaFrontierDisposition.QUARANTINE
            rationale = "result is absent, foreign-context, contradictory, or mismatched"
        prohibited = contracts.by_operation(row.operation).prohibited_claims
        body = {"record_id": row.record_id, "operation": row.operation, "state": row.observed_state, "disposition": disposition, "rationale": rationale, "prohibited_claims": prohibited}
        decisions.append(CohortBetaFrontierPolicyDecision(row.record_id, row.operation, row.observed_state, disposition, rationale, prohibited, content_hash(body, prefix="policy")))
    values = tuple(decisions)
    body = {"decisions": values}
    return CohortBetaFrontierPolicy(values, sum(item.disposition is CohortBetaFrontierDisposition.PUBLISH for item in values), sum(item.disposition is CohortBetaFrontierDisposition.REVIEW for item in values), sum(item.disposition is CohortBetaFrontierDisposition.QUARANTINE for item in values), content_hash(body, prefix="policy-set"))


__all__ = ["CohortBetaFrontierDisposition", "CohortBetaFrontierPolicy", "CohortBetaFrontierPolicyDecision", "materialize_cohort_beta_frontier_policy"]
