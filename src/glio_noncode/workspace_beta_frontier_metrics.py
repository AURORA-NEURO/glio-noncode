"""Descriptive metrics for topology, chain, posterior, and table outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_public_data import BetaFrontierOperation


@dataclass(frozen=True, slots=True)
class BetaFrontierMetric:
    """Ratio or count with numerator and denominator retained."""

    metric_id: str
    value: float
    unit: str
    numerator: int
    denominator: int
    interpretation: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("metric_id", "unit", "interpretation", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.numerator < 0 or self.denominator < 0:
            raise ValueError("beta frontier metric counts cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierMetricsReport:
    """Metric collection with stable lookup."""

    fixture_id: str
    metrics: tuple[BetaFrontierMetric, ...]
    content_address: str

    def by_id(self, metric_id: str) -> BetaFrontierMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _metric(metric_id: str, numerator: int, denominator: int, unit: str, interpretation: str) -> BetaFrontierMetric:
    body = {"metric_id": metric_id, "value": numerator / denominator if denominator else 0.0, "unit": unit, "numerator": numerator, "denominator": denominator, "interpretation": interpretation}
    return BetaFrontierMetric(**body, content_address=content_hash(body))


def measure_beta_frontier(evaluation: BetaFrontierEvaluation) -> BetaFrontierMetricsReport:
    """Measure fixture behavior without treating a metric as a claim."""

    total = len(evaluation.executions)
    positives = tuple(item for item in evaluation.executions if item.role.value == "positive")
    controls = tuple(item for item in evaluation.executions if item.role.value == "control")
    metrics = (
        _metric("positive_acceptance_rate", sum(item.accepted for item in positives), len(positives), "ratio", "positive paths accepted"),
        _metric("control_rejection_rate", sum(not item.accepted for item in controls), len(controls), "ratio", "control paths remain unpromoted"),
        _metric("check_pass_rate", evaluation.passed_checks, len(evaluation.checks), "ratio", "fixture assertions pass"),
        _metric("addressed_execution_rate", sum(item.content_address.startswith("sha256:") for item in evaluation.executions), total, "ratio", "execution receipts are addressed"),
        _metric("topology_case_count", sum(item.operation is BetaFrontierOperation.TOPOLOGY_VIEWPORT for item in evaluation.executions), total, "share", "topology cases in package"),
        _metric("causal_case_count", sum(item.operation is BetaFrontierOperation.CAUSAL_CHAIN for item in evaluation.executions), total, "share", "causal cases in package"),
        _metric("posterior_case_count", sum(item.operation is BetaFrontierOperation.POSTERIOR_DECOMPOSITION for item in evaluation.executions), total, "share", "posterior cases in package"),
        _metric("table_case_count", sum(item.operation is BetaFrontierOperation.EVIDENCE_TABLE for item in evaluation.executions), total, "share", "table cases in package"),
        _metric("foreign_context_visible", sum("context_mismatch" in item.issue_codes for item in evaluation.executions), total, "share", "foreign context controls are explicit"),
        _metric("partial_state_visible", sum(item.state in {"partial", "incomplete"} for item in evaluation.executions), total, "share", "unresolved projection state remains visible"),
        _metric("contradiction_visible", sum(item.state == "contradictory" for item in evaluation.executions), total, "share", "contradictory chain state remains visible"),
        _metric("empty_result_visible", sum(item.state == "absent" for item in evaluation.executions), total, "share", "empty projections remain absent"),
        _metric("output_retention_rate", sum(bool(item.output) for item in evaluation.executions), total, "ratio", "every execution retains output"),
    )
    body = {"fixture_id": evaluation.fixture_id, "metrics": metrics}
    return BetaFrontierMetricsReport(fixture_id=evaluation.fixture_id, metrics=metrics, content_address=content_hash(body))


__all__ = ["BetaFrontierMetric", "BetaFrontierMetricsReport", "measure_beta_frontier"]
