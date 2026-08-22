"""Metrics for C09-C12 expected-path agreement and operation balance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierMetric:
    metric_id: str
    value: float
    numerator: int
    denominator: int
    interpretation: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id or self.denominator < 0 or self.numerator < 0:
            raise ValidationError("metric identity or counts are invalid")
        if self.denominator and not 0 <= self.value <= 1:
            raise ValidationError("ratio metrics must be between zero and one")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierMetrics:
    metrics: tuple[ChromatinAlphaFrontierMetric, ...]
    operation_counts: dict[str, int]
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValidationError("metrics cannot be empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def metric(self, metric_id: str) -> ChromatinAlphaFrontierMetric:
        for metric in self.metrics:
            if metric.metric_id == metric_id:
                return metric
        raise KeyError(metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_alpha_frontier_metrics(
    evaluation: ChromatinAlphaFrontierEvaluation,
) -> ChromatinAlphaFrontierMetrics:
    total = len(evaluation.records)
    positives = evaluation.positive_count
    controls = evaluation.control_count
    values = (
        ChromatinAlphaFrontierMetric(
            "state_match_rate",
            evaluation.state_match_count / total,
            evaluation.state_match_count,
            total,
            "expected state agreement",
        ),
        ChromatinAlphaFrontierMetric(
            "issue_match_rate",
            evaluation.issue_match_count / total,
            evaluation.issue_match_count,
            total,
            "expected issue floors observed",
        ),
        ChromatinAlphaFrontierMetric(
            "positive_acceptance",
            sum(item.accepted for item in evaluation.records if item.role == "positive")
            / positives,
            sum(item.accepted for item in evaluation.records if item.role == "positive"),
            positives,
            "positive aggregate rows accepted",
        ),
        ChromatinAlphaFrontierMetric(
            "control_path_coverage",
            sum(item.accepted for item in evaluation.records if item.role == "control") / controls,
            sum(item.accepted for item in evaluation.records if item.role == "control"),
            controls,
            "control paths reconciled",
        ),
        ChromatinAlphaFrontierMetric(
            "receipt_completeness",
            sum(item.adapter.content_address.startswith("sha256:") for item in evaluation.records)
            / total,
            sum(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            total,
            "result receipts present",
        ),
    )
    operation_counts = {
        operation.value: sum(item.adapter.operation is operation for item in evaluation.records)
        for operation in ChromatinAlphaFrontierOperation
    }
    state_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    for item in evaluation.records:
        state_counts[item.observed_state] = state_counts.get(item.observed_state, 0) + 1
        for issue in item.observed_issue_codes:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    return ChromatinAlphaFrontierMetrics(
        values,
        operation_counts,
        state_counts,
        issue_counts,
        all(metric.value == 1 for metric in values),
    )


__all__ = [
    "ChromatinAlphaFrontierMetric",
    "ChromatinAlphaFrontierMetrics",
    "build_chromatin_alpha_frontier_metrics",
]
