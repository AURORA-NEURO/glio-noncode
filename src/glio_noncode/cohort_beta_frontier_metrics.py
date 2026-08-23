"""Coverage and state metrics for the C05-C08 aggregate evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta import CohortBetaState
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierOperationMetric:
    operation: str
    total: int
    accepted: int
    supported: int
    partial: int
    absent: int
    out_of_domain: int
    contradictory: int
    acceptance_percent: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierMetrics:
    total_rows: int
    accepted_rows: int
    supported_rows: int
    control_rows: int
    mismatch_rows: int
    acceptance_percent: float
    operations: tuple[CohortBetaFrontierOperationMetric, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_cohort_beta_frontier(evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierMetrics:
    operation_metrics: list[CohortBetaFrontierOperationMetric] = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = tuple(item for item in evaluation.rows if item.operation == operation)
        counts = {state.value: sum(item.observed_state is state for item in rows) for state in CohortBetaState}
        body = {"operation": operation, "total": len(rows), "accepted": sum(item.accepted for item in rows), "counts": counts}
        operation_metrics.append(CohortBetaFrontierOperationMetric(operation, len(rows), sum(item.accepted for item in rows), counts["supported"], counts["partial"], counts["absent"], counts["out_of_domain"], counts["contradictory"], round(100 * sum(item.accepted for item in rows) / max(1, len(rows)), 2), content_hash(body, prefix="operation-metric")))
    body = {"total_rows": len(evaluation.rows), "accepted_rows": sum(item.accepted for item in evaluation.rows), "supported_rows": evaluation.supported_count, "control_rows": evaluation.control_count, "mismatch_rows": evaluation.mismatch_count, "operations": operation_metrics}
    return CohortBetaFrontierMetrics(len(evaluation.rows), sum(item.accepted for item in evaluation.rows), evaluation.supported_count, evaluation.control_count, evaluation.mismatch_count, round(100 * sum(item.accepted for item in evaluation.rows) / max(1, len(evaluation.rows)), 2), tuple(operation_metrics), content_hash(body, prefix="metrics"))


__all__ = ["CohortBetaFrontierMetrics", "CohortBetaFrontierOperationMetric", "measure_cohort_beta_frontier"]
