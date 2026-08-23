"""Coverage and control metrics for the C01-C04 evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_public_data import CohortFoundationOperation, CohortFoundationRole


@dataclass(frozen=True, slots=True)
class CohortFoundationOperationMetric:
    operation: CohortFoundationOperation
    total: int
    positive: int
    controls: int
    accepted: int
    supported: int
    partial: int
    absent: int
    out_of_domain: int
    abstained: int
    issue_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationMetrics:
    execution_count: int
    accepted_count: int
    positive_count: int
    control_count: int
    operation_metrics: tuple[CohortFoundationOperationMetric, ...]
    distinct_sources: tuple[str, ...]
    context_keys: tuple[str, ...]
    content_address: str

    def by_operation(self, operation: CohortFoundationOperation) -> CohortFoundationOperationMetric:
        return next(item for item in self.operation_metrics if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_cohort_foundation_frontier(evaluation: CohortFoundationEvaluation) -> CohortFoundationMetrics:
    metrics: list[CohortFoundationOperationMetric] = []
    for operation in CohortFoundationOperation:
        values = tuple(item for item in evaluation.executions if item.operation is operation)
        counts = {state: sum(item.actual_state == state for item in values) for state in ("supported", "partial", "absent", "out_of_domain", "abstained")}
        body = {"operation": operation, "total": len(values), "accepted": sum(item.accepted for item in values), "states": counts}
        metrics.append(CohortFoundationOperationMetric(operation, len(values), sum(item.role is CohortFoundationRole.POSITIVE for item in values), sum(item.role is CohortFoundationRole.CONTROL for item in values), sum(item.accepted for item in values), counts["supported"], counts["partial"], counts["absent"], counts["out_of_domain"], counts["abstained"], sum(len(item.issues) for item in values), content_hash(body)))
    sources = tuple(sorted({source_id for item in evaluation.executions for source_id in item.source_ids}))
    contexts = tuple(sorted({str(item.output.get("context_key", "target")) for item in evaluation.executions}))
    body = {"execution_count": len(evaluation.executions), "accepted_count": sum(item.accepted for item in evaluation.executions), "metrics": metrics, "sources": sources, "contexts": contexts}
    return CohortFoundationMetrics(len(evaluation.executions), sum(item.accepted for item in evaluation.executions), sum(item.role is CohortFoundationRole.POSITIVE for item in evaluation.executions), sum(item.role is CohortFoundationRole.CONTROL for item in evaluation.executions), tuple(metrics), sources, contexts, content_hash(body))


__all__ = ["CohortFoundationMetrics", "CohortFoundationOperationMetric", "measure_cohort_foundation_frontier"]
