"""Decision trace ledger tying every result to policy and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_policy import CohortBetaFrontierPolicy
from .cohort_beta_frontier_reconciliation import CohortBetaFrontierReconciliation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierTraceStep:
    record_id: str
    operation: str
    result_address: str
    policy_address: str
    reconciliation_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierTraceLedger:
    steps: tuple[CohortBetaFrontierTraceStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_trace_ledger(evaluation: CohortBetaFrontierEvaluation, policy: CohortBetaFrontierPolicy, reconciliation: CohortBetaFrontierReconciliation) -> CohortBetaFrontierTraceLedger:
    steps = tuple(CohortBetaFrontierTraceStep(row.record_id, row.operation, row.content_address, policy.for_record(row.record_id).content_address, next(item for item in reconciliation.items if item.record_id == row.record_id).content_address, content_hash({"record_id": row.record_id, "operation": row.operation}, prefix="trace")) for row in evaluation.rows)
    return CohortBetaFrontierTraceLedger(steps, len(steps) == len(evaluation.rows), content_hash(steps, prefix="trace-ledger"))


__all__ = ["CohortBetaFrontierTraceLedger", "CohortBetaFrontierTraceStep", "build_cohort_beta_frontier_trace_ledger"]
