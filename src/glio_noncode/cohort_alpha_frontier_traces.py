"""Decision traces joining evaluation, policy, and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy, CohortAlphaFrontierReconciliation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierTraceStep:
    record_id: str
    operation: str
    result_address: str
    policy_address: str
    reconciliation_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierTraceLedger:
    steps: tuple[CohortAlphaFrontierTraceStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_trace_ledger(evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy, reconciliation: CohortAlphaFrontierReconciliation) -> CohortAlphaFrontierTraceLedger:
    steps = tuple(CohortAlphaFrontierTraceStep(row.record_id, row.operation, row.content_address, policy.for_record(row.record_id).content_address, next(item for item in reconciliation.items if item.record_id == row.record_id).content_address, content_hash({"record_id": row.record_id, "operation": row.operation}, prefix="alpha-trace")) for row in evaluation.rows)
    return CohortAlphaFrontierTraceLedger(steps, len(steps) == len(evaluation.rows), content_hash(steps, prefix="alpha-traces"))


__all__ = ["CohortAlphaFrontierTraceLedger", "CohortAlphaFrontierTraceStep", "build_cohort_alpha_frontier_trace_ledger"]
