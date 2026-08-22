"""Coverage and control metrics for Domain 12 convergence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_fixture_eval import CohortFrontierEvaluation
from .cohort_frontier_public_data import CohortFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFrontierMetric:
    metric_id: str
    operation: str
    value: float
    numerator: int
    denominator: int
    interpretation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierMetricsReport:
    metrics: tuple[CohortFrontierMetric, ...]
    evaluation_address: str
    content_address: str

    def by_id(self, metric_id: str) -> CohortFrontierMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_cohort_frontier(evaluation: CohortFrontierEvaluation) -> CohortFrontierMetricsReport:
    metrics: list[CohortFrontierMetric] = []
    def add(metric_id: str, operation: str, numerator: int, denominator: int, interpretation: str) -> None:
        body = {"metric_id": metric_id, "operation": operation, "value": round(numerator / denominator, 6) if denominator else 0.0, "numerator": numerator, "denominator": denominator, "interpretation": interpretation}
        metrics.append(CohortFrontierMetric(**body, content_address=content_hash(body)))
    add("overall_check_pass_rate", "all", evaluation.passed_checks, len(evaluation.checks), "fixture checks pass")
    add("positive_acceptance_rate", "positive", sum(item.accepted for item in evaluation.executions if item.role.value == "positive"), sum(item.role.value == "positive" for item in evaluation.executions), "positive paths are accepted")
    add("control_rejection_rate", "control", sum(not item.accepted for item in evaluation.executions if item.role.value == "control"), sum(item.role.value == "control" for item in evaluation.executions), "controls remain non-accepted")
    for operation in CohortFrontierOperation:
        rows = tuple(item for item in evaluation.executions if item.operation is operation)
        add(f"{operation.value}_acceptance_rate", operation.value, sum(item.accepted for item in rows), len(rows), "operation acceptance remains role-aware")
        add(f"{operation.value}_issue_free_rate", operation.value, sum(not item.issue_codes for item in rows), len(rows), "operation issue-free rate")
    body = {"metrics": tuple(metrics), "evaluation_address": evaluation.content_address}
    return CohortFrontierMetricsReport(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierMetric", "CohortFrontierMetricsReport", "measure_cohort_frontier"]
