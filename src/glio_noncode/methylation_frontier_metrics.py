"""Metrics for expected-path agreement in the methylation tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import MethylationFrontierEvaluation
from .methylation_frontier_public_data import MethylationFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierMetric:
    metric_id: str
    value: float
    numerator: int
    denominator: int
    interpretation: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id or self.denominator < 0 or self.numerator < 0:
            raise ValidationError("metric identity and counts are invalid")
        if self.denominator and not 0 <= self.value <= 1:
            raise ValidationError("ratio metric must be between zero and one")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierMetrics:
    metrics: tuple[MethylationFrontierMetric, ...]
    operation_counts: dict[str, int]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValidationError("metrics cannot be empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_methylation_frontier_metrics(
    evaluation: MethylationFrontierEvaluation,
) -> MethylationFrontierMetrics:
    total = len(evaluation.records)
    positive_total = evaluation.positive_count
    control_total = evaluation.control_count
    metrics = (
        MethylationFrontierMetric(
            "state_match_rate",
            evaluation.state_match_count / total,
            evaluation.state_match_count,
            total,
            "expected state agreement",
        ),
        MethylationFrontierMetric(
            "issue_match_rate",
            evaluation.issue_match_count / total,
            evaluation.issue_match_count,
            total,
            "expected issue-path coverage",
        ),
        MethylationFrontierMetric(
            "positive_acceptance",
            sum(item.accepted for item in evaluation.records if item.role == "positive")
            / positive_total,
            sum(item.accepted for item in evaluation.records if item.role == "positive"),
            positive_total,
            "positive aggregate cases accepted",
        ),
        MethylationFrontierMetric(
            "control_acceptance",
            sum(item.accepted for item in evaluation.records if item.role == "control")
            / control_total,
            sum(item.accepted for item in evaluation.records if item.role == "control"),
            control_total,
            "controls accepted on their expected boundary paths",
        ),
    )
    counts = {
        operation.value: sum(item.adapter.operation is operation for item in evaluation.records)
        for operation in MethylationFrontierOperation
    }
    return MethylationFrontierMetrics(metrics, counts, all(metric.value == 1 for metric in metrics))


__all__ = [
    "MethylationFrontierMetric",
    "MethylationFrontierMetrics",
    "build_methylation_frontier_metrics",
]
