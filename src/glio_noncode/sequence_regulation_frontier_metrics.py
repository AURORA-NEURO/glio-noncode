"""Deterministic quality metrics for C09-C12 execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_public_data import SequenceRegulationOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationMetric:
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
class SequenceRegulationMetrics:
    metrics: tuple[SequenceRegulationMetric, ...]
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


def build_sequence_regulation_metrics(
    evaluation: SequenceRegulationEvaluation,
) -> SequenceRegulationMetrics:
    total = len(evaluation.records)
    matched = evaluation.state_match_count
    issue_matched = evaluation.issue_match_count
    metrics = (
        SequenceRegulationMetric(
            "state_match_rate", matched / total, matched, total, "expected state agreement"
        ),
        SequenceRegulationMetric(
            "issue_match_rate",
            issue_matched / total,
            issue_matched,
            total,
            "expected issue-path coverage",
        ),
        SequenceRegulationMetric(
            "positive_acceptance",
            sum(item.accepted for item in evaluation.records if item.role == "positive")
            / evaluation.positive_count,
            sum(item.accepted for item in evaluation.records if item.role == "positive"),
            evaluation.positive_count,
            "positive aggregate cases accepted",
        ),
        SequenceRegulationMetric(
            "control_acceptance",
            sum(item.accepted for item in evaluation.records if item.role == "control")
            / evaluation.control_count,
            sum(item.accepted for item in evaluation.records if item.role == "control"),
            evaluation.control_count,
            "boundary controls accepted",
        ),
    )
    counts = {
        operation.value: sum(item.adapter.operation is operation for item in evaluation.records)
        for operation in SequenceRegulationOperation
    }
    return SequenceRegulationMetrics(metrics, counts, all(metric.value == 1 for metric in metrics))


__all__ = [
    "SequenceRegulationMetric",
    "SequenceRegulationMetrics",
    "build_sequence_regulation_metrics",
]
