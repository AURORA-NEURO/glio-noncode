"""Metrics for accepted paths, control retention, and surface coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation
from .workspace_gamma_frontier_public_data import GammaFrontierOperation, GammaFrontierRole


@dataclass(frozen=True, slots=True)
class GammaFrontierMetric:
    """One numerator/denominator metric with an explicit interpretation."""

    metric_id: str
    numerator: int
    denominator: int
    unit: str
    interpretation: str
    content_address: str

    @property
    def ratio(self) -> float | None:
        return None if self.denominator == 0 else self.numerator / self.denominator

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"ratio": self.ratio}


@dataclass(frozen=True, slots=True)
class GammaFrontierMetricsReport:
    """Full metric set for one evaluation."""

    fixture_id: str
    metrics: tuple[GammaFrontierMetric, ...]
    content_address: str

    def by_id(self, metric_id: str) -> GammaFrontierMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def by_operation(self, operation: GammaFrontierOperation) -> tuple[GammaFrontierMetric, ...]:
        return tuple(item for item in self.metrics if item.metric_id.startswith(operation.value))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _metric(
    metric_id: str, numerator: int, denominator: int, unit: str, interpretation: str
) -> GammaFrontierMetric:
    body = {
        "metric_id": metric_id,
        "numerator": numerator,
        "denominator": denominator,
        "unit": unit,
        "interpretation": interpretation,
    }
    return GammaFrontierMetric(**body, content_address=content_hash(body))


def measure_gamma_frontier(evaluation: GammaFrontierEvaluation) -> GammaFrontierMetricsReport:
    """Compute transparent counts without collapsing control outcomes."""

    executions = evaluation.executions
    metrics: list[GammaFrontierMetric] = [
        _metric(
            "records.accepted",
            sum(item.accepted for item in executions),
            len(executions),
            "records",
            "execution receipts retained without a rejected row",
        ),
        _metric(
            "records.positive",
            sum(item.role is GammaFrontierRole.POSITIVE for item in executions),
            len(executions),
            "records",
            "positive path share",
        ),
        _metric(
            "records.control",
            sum(item.role is GammaFrontierRole.CONTROL for item in executions),
            len(executions),
            "records",
            "control path share",
        ),
        _metric(
            "checks.passed",
            evaluation.passed_checks,
            len(evaluation.checks),
            "checks",
            "expected-versus-observed check pass rate",
        ),
        _metric(
            "checks.failed",
            len(evaluation.failed_check_ids),
            len(evaluation.checks),
            "checks",
            "visible failed check rate",
        ),
    ]
    for operation in GammaFrontierOperation:
        rows = tuple(item for item in executions if item.operation is operation)
        metrics.extend(
            (
                _metric(
                    f"{operation.value}.records",
                    len(rows),
                    len(executions),
                    "records",
                    "surface record share",
                ),
                _metric(
                    f"{operation.value}.controls",
                    sum(item.role is GammaFrontierRole.CONTROL for item in rows),
                    len(rows),
                    "records",
                    "surface control retention",
                ),
                _metric(
                    f"{operation.value}.issues",
                    sum(bool(item.issue_codes) for item in rows),
                    len(rows),
                    "records",
                    "surface rows with explicit issue evidence",
                ),
            )
        )
    body = {"fixture_id": evaluation.fixture_id, "metrics": tuple(metrics)}
    return GammaFrontierMetricsReport(**body, content_address=content_hash(body))


__all__ = ["GammaFrontierMetric", "GammaFrontierMetricsReport", "measure_gamma_frontier"]
