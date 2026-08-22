"""Descriptive coverage metrics for Domain 13 planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_public_data import ValidationFrontierOperation, ValidationFrontierRole


@dataclass(frozen=True, slots=True)
class ValidationFrontierMetric:
    metric_id: str
    value: float
    numerator: int
    denominator: int
    scope: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierMetricsReport:
    metrics: tuple[ValidationFrontierMetric, ...]
    content_address: str

    def by_id(self, metric_id: str) -> ValidationFrontierMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _metric(metric_id: str, numerator: int, denominator: int, scope: str) -> ValidationFrontierMetric:
    value = round(numerator / denominator, 6) if denominator else 0.0
    body = {"metric_id": metric_id, "value": value, "numerator": numerator, "denominator": denominator, "scope": scope}
    return ValidationFrontierMetric(**body, content_address=content_hash(body))


def measure_validation_frontier(evaluation: ValidationFrontierEvaluation) -> ValidationFrontierMetricsReport:
    total = len(evaluation.executions)
    accepted = sum(item.accepted for item in evaluation.executions)
    controls = tuple(item for item in evaluation.executions if item.role is ValidationFrontierRole.CONTROL)
    metrics = [_metric("overall_check_pass_rate", evaluation.passed_checks, len(evaluation.checks), "overall"), _metric("positive_acceptance_rate", sum(item.accepted for item in evaluation.executions if item.role is ValidationFrontierRole.POSITIVE), sum(item.role is ValidationFrontierRole.POSITIVE for item in evaluation.executions), "positive"), _metric("control_rejection_rate", sum(not item.accepted for item in controls), len(controls), "control"), _metric("accepted_execution_rate", accepted, total, "overall"), _metric("partial_state_rate", sum(item.state == "partial" for item in evaluation.executions), total, "overall"), _metric("blocked_state_rate", sum(item.state == "blocked" for item in evaluation.executions), total, "overall"), _metric("ready_state_rate", sum(item.state == "ready_for_review" for item in evaluation.executions), total, "overall"), _metric("invalid_state_rate", sum(item.state == "invalid" for item in evaluation.executions), total, "overall"), _metric("issue_visible_rate", sum(bool(item.issue_codes) for item in evaluation.executions), total, "overall")]
    for operation in ValidationFrontierOperation:
        values = tuple(item for item in evaluation.executions if item.operation is operation)
        metrics.append(_metric(f"{operation.value}_acceptance_rate", sum(item.accepted for item in values), len(values), operation.value))
    body = {"metrics": tuple(metrics)}
    return ValidationFrontierMetricsReport(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierMetric", "ValidationFrontierMetricsReport", "measure_validation_frontier"]
