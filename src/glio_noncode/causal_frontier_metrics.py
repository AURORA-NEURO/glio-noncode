"""Auditable metrics for evidence completeness, controls, and abstention."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_fixture_eval import CausalFrontierEvaluation
from .causal_frontier_public_data import CausalFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFrontierMetric:
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
class CausalFrontierMetricsReport:
    metrics: tuple[CausalFrontierMetric, ...]
    evaluation_address: str
    content_address: str

    def by_id(self, metric_id: str) -> CausalFrontierMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_causal_frontier(evaluation: CausalFrontierEvaluation) -> CausalFrontierMetricsReport:
    metrics: list[CausalFrontierMetric] = []

    def add(metric_id: str, operation: str, numerator: int, denominator: int, interpretation: str) -> None:
        body = {
            "metric_id": metric_id,
            "operation": operation,
            "value": round(numerator / denominator, 6) if denominator else 0.0,
            "numerator": numerator,
            "denominator": denominator,
            "interpretation": interpretation,
        }
        metrics.append(CausalFrontierMetric(**body, content_address=content_hash(body)))

    add("overall_check_pass_rate", "all", evaluation.passed_checks, len(evaluation.checks), "all fixture checks pass")
    add("positive_acceptance_rate", "positive", sum(item.accepted for item in evaluation.executions if item.role.value == "positive"), sum(item.role.value == "positive" for item in evaluation.executions), "positive fixture records are accepted")
    add("control_rejection_rate", "control", sum(not item.accepted for item in evaluation.executions if item.role.value == "control"), sum(item.role.value == "control" for item in evaluation.executions), "control records remain non-accepted")
    for operation in CausalFrontierOperation:
        rows = tuple(item for item in evaluation.executions if item.operation is operation)
        add(f"{operation.value}_execution_acceptance", operation.value, sum(item.accepted for item in rows), len(rows), "operation receipts pass bounded acceptance")
        issue_counts = [len(item.issue_codes) for item in rows]
        add(f"{operation.value}_issue_free_rate", operation.value, sum(count == 0 for count in issue_counts), len(rows), "operation outputs have no issue codes")
    add("issue_free_execution_rate", "all", sum(not item.issue_codes for item in evaluation.executions), len(evaluation.executions), "executions contain no issue codes")
    add("mean_issue_count_inverse", "all", sum(max(0, 3 - len(item.issue_codes)) for item in evaluation.executions), 3 * len(evaluation.executions), "lower issue density is better")
    body = {"metrics": tuple(metrics), "evaluation_address": evaluation.content_address}
    return CausalFrontierMetricsReport(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierMetric", "CausalFrontierMetricsReport", "measure_causal_frontier"]
