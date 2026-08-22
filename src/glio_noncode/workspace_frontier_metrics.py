"""Deterministic descriptive metrics for workspace evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_public_data import WorkspaceFrontierOperation


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierMetric:
    metric_id: str
    value: float
    unit: str
    numerator: int
    denominator: int
    interpretation: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.metric_id, "metric_id")
        require_non_empty(self.unit, "unit")
        require_non_empty(self.interpretation, "interpretation")
        if self.denominator < 0 or self.numerator < 0:
            raise ValueError("workspace metric counts cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierMetricsReport:
    fixture_id: str
    metrics: tuple[WorkspaceFrontierMetric, ...]
    content_address: str

    def by_id(self, metric_id: str) -> WorkspaceFrontierMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _metric(metric_id: str, numerator: int, denominator: int, unit: str, interpretation: str) -> WorkspaceFrontierMetric:
    value = numerator / denominator if denominator else 0.0
    body = {"metric_id": metric_id, "value": value, "unit": unit, "numerator": numerator, "denominator": denominator, "interpretation": interpretation}
    return WorkspaceFrontierMetric(**body, content_address=content_hash(body))


def measure_workspace_frontier(evaluation: WorkspaceFrontierEvaluation) -> WorkspaceFrontierMetricsReport:
    total = len(evaluation.executions)
    positives = tuple(item for item in evaluation.executions if item.role.value == "positive")
    controls = tuple(item for item in evaluation.executions if item.role.value == "control")
    metrics = (
        _metric("positive_acceptance_rate", sum(item.accepted for item in positives), len(positives), "ratio", "positive fixture paths accepted"),
        _metric("control_rejection_rate", sum(not item.accepted for item in controls), len(controls), "ratio", "control paths are not promoted"),
        _metric("execution_check_pass_rate", evaluation.passed_checks, len(evaluation.checks), "ratio", "evaluation checks pass"),
        _metric("context_preservation_rate", sum("context" in item.check_id and item.passed for item in evaluation.checks), sum("context" in item.check_id for item in evaluation.checks), "ratio", "execution context checks pass"),
        _metric("addressed_execution_rate", sum(item.content_address.startswith("sha256:") for item in evaluation.executions), total, "ratio", "execution receipts are content addressed"),
        _metric("case_surface_count", sum(item.operation is WorkspaceFrontierOperation.CASE_WORKSPACE for item in evaluation.executions), total, "ratio", "case surface share of fixture"),
        _metric("cohort_surface_count", sum(item.operation is WorkspaceFrontierOperation.COHORT_WORKSPACE for item in evaluation.executions), total, "ratio", "cohort surface share of fixture"),
        _metric("variant_surface_count", sum(item.operation is WorkspaceFrontierOperation.VARIANT_EXPLORER for item in evaluation.executions), total, "ratio", "variant surface share of fixture"),
        _metric("track_surface_count", sum(item.operation is WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER for item in evaluation.executions), total, "ratio", "track surface share of fixture"),
        _metric("review_state_rate", sum(item.state != "supported" for item in evaluation.executions), total, "ratio", "non-supported states remain review-visible"),
        _metric("source_boundary_check_rate", 1 if evaluation.accepted else 0, 1, "ratio", "public aggregate boundary accepted"),
        _metric("issue_visibility_rate", sum(bool(item.issue_codes) == (item.state != "supported") for item in evaluation.executions), total, "ratio", "issues track unresolved state"),
        _metric("output_retention_rate", sum(bool(item.output) for item in evaluation.executions), total, "ratio", "surface output is retained"),
    )
    body = {"fixture_id": evaluation.fixture_id, "metrics": metrics}
    return WorkspaceFrontierMetricsReport(fixture_id=evaluation.fixture_id, metrics=metrics, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierMetric", "WorkspaceFrontierMetricsReport", "measure_workspace_frontier"]
