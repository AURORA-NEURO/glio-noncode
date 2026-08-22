"""Operation-level metrics for context-alpha evidence."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierMetric:
    metric_id: str
    value: float
    unit: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id or not self.unit or not self.detail:
            raise ValidationError("alpha metric is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierMetrics:
    metrics: tuple[CellContextAlphaFrontierMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValidationError("alpha metrics are empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, metric_id: str) -> CellContextAlphaFrontierMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_alpha_frontier_metrics(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierMetrics:
    result_counts = tuple(
        float(item.adapter.measurements.get("result_count", 0)) for item in evaluation.records
    )
    deltas = tuple(
        abs(float(value.get("support_delta", 0.0) or 0.0))
        for row in evaluation.records
        for value in row.adapter.measurements.get("results", ())
        if isinstance(value, dict)
    )
    metrics = (
        CellContextAlphaFrontierMetric(
            "record_count", float(len(evaluation.records)), "records", "rows executed"
        ),
        CellContextAlphaFrontierMetric(
            "state_match_rate",
            evaluation.state_match_count / len(evaluation.records),
            "ratio",
            "expected state agreement",
        ),
        CellContextAlphaFrontierMetric(
            "issue_floor_rate",
            evaluation.issue_match_count / len(evaluation.records),
            "ratio",
            "issue floor agreement",
        ),
        CellContextAlphaFrontierMetric(
            "mean_result_count",
            round(fmean(result_counts), 6),
            "results",
            "mean primitive result count",
        ),
        CellContextAlphaFrontierMetric(
            "mean_delta_magnitude",
            round(fmean(deltas) if deltas else 0.0, 6),
            "bounded_score",
            "mean support delta magnitude",
        ),
        CellContextAlphaFrontierMetric(
            "ambiguity_count",
            float(sum(item.observed_state == "ambiguous" for item in evaluation.records)),
            "records",
            "niche, territory, and phase ambiguity controls",
        ),
        CellContextAlphaFrontierMetric(
            "partial_count",
            float(sum(item.observed_state == "partial" for item in evaluation.records)),
            "records",
            "parser or one-sided evidence controls",
        ),
        CellContextAlphaFrontierMetric(
            "domain_refusal_count",
            float(sum(item.observed_state == "out_of_domain" for item in evaluation.records)),
            "records",
            "exact context refusals",
        ),
    )
    return CellContextAlphaFrontierMetrics(
        metrics, evaluation.accepted and all(item.value >= 0 for item in metrics)
    )


__all__ = [
    "CellContextAlphaFrontierMetric",
    "CellContextAlphaFrontierMetrics",
    "build_cell_context_alpha_frontier_metrics",
]
