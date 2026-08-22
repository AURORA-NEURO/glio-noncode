"""Release metrics for the four context-track operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierMetric:
    metric_id: str
    value: float
    required: float
    passed: bool
    unit: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id or not self.unit or not self.detail:
            raise ValidationError("metric is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierMetrics:
    metrics: tuple[ChromatinContextFrontierMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValidationError("metrics require at least one value")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_metric_ids(self) -> tuple[str, ...]:
        return tuple(item.metric_id for item in self.metrics if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_metric_ids": list(self.failed_metric_ids)}


def build_chromatin_context_frontier_metrics(
    evaluation: ChromatinContextFrontierEvaluation,
) -> ChromatinContextFrontierMetrics:
    positive = len(evaluation.positive_rows)
    controls = len(evaluation.control_rows)
    supported_positive = sum(
        item.observed_state == "supported" for item in evaluation.positive_rows
    )
    state_rate = supported_positive / positive if positive else 0.0
    metrics = (
        ChromatinContextFrontierMetric(
            "positive_support_rate",
            state_rate,
            1.0,
            state_rate == 1.0,
            "ratio",
            "all four positive paths must be supported",
        ),
        ChromatinContextFrontierMetric(
            "control_coverage",
            min(controls / 12, 1.0),
            1.0,
            controls == 12,
            "ratio",
            "twelve controls remain in the evaluation",
        ),
        ChromatinContextFrontierMetric(
            "state_match_rate",
            evaluation.state_match_count / len(evaluation.records),
            1.0,
            evaluation.state_match_count == len(evaluation.records),
            "ratio",
            "expected and observed states reconcile",
        ),
        ChromatinContextFrontierMetric(
            "issue_floor_rate",
            evaluation.issue_match_count / len(evaluation.records),
            1.0,
            evaluation.issue_match_count == len(evaluation.records),
            "ratio",
            "expected issue floors reconcile",
        ),
        ChromatinContextFrontierMetric(
            "operation_coverage",
            len({item.operation for item in evaluation.records}) / 4,
            1.0,
            len({item.operation for item in evaluation.records}) == 4,
            "ratio",
            "all four operations execute",
        ),
        ChromatinContextFrontierMetric(
            "receipt_rate",
            sum(bool(item.adapter.content_address) for item in evaluation.records)
            / len(evaluation.records),
            1.0,
            all(bool(item.adapter.content_address) for item in evaluation.records),
            "ratio",
            "each adapter result has a content receipt",
        ),
        ChromatinContextFrontierMetric(
            "foreign_context_visibility",
            sum(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            1.0,
            any(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            "rows",
            "foreign-context controls remain visible",
        ),
        ChromatinContextFrontierMetric(
            "uncertainty_visibility",
            sum(
                item.observed_state in {"ambiguous", "partial", "abstained"}
                for item in evaluation.control_rows
            ),
            1.0,
            any(
                item.observed_state in {"ambiguous", "partial", "abstained"}
                for item in evaluation.control_rows
            ),
            "rows",
            "uncertain controls remain visible",
        ),
    )
    return ChromatinContextFrontierMetrics(metrics, all(item.passed for item in metrics))


__all__ = [
    "ChromatinContextFrontierMetric",
    "ChromatinContextFrontierMetrics",
    "build_chromatin_context_frontier_metrics",
]
