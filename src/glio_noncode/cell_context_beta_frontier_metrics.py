"""Deterministic metrics for prior-family coverage and uncertainty."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierMetric:
    metric_id: str
    value: float
    unit: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id or not self.unit or not self.detail:
            raise ValidationError("beta metric is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierMetrics:
    metrics: tuple[CellContextBetaFrontierMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValidationError("beta metrics are empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, metric_id: str) -> CellContextBetaFrontierMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_beta_frontier_metrics(
    evaluation: CellContextBetaFrontierEvaluation,
) -> CellContextBetaFrontierMetrics:
    uncertainty = tuple(
        float(item.adapter.measurements.get("uncertainty", 1.0)) for item in evaluation.records
    )
    candidates = tuple(
        len(item.adapter.measurements.get("candidate_ids", ())) for item in evaluation.records
    )
    supported = sum(item.observed_state == "supported" for item in evaluation.records)
    metrics = (
        CellContextBetaFrontierMetric(
            "record_count", float(len(evaluation.records)), "records", "records executed"
        ),
        CellContextBetaFrontierMetric(
            "state_match_rate",
            round(evaluation.state_match_count / len(evaluation.records), 6),
            "ratio",
            "declared state agreement",
        ),
        CellContextBetaFrontierMetric(
            "issue_floor_rate",
            round(evaluation.issue_match_count / len(evaluation.records), 6),
            "ratio",
            "minimum issue-code agreement",
        ),
        CellContextBetaFrontierMetric(
            "supported_rate",
            round(supported / len(evaluation.records), 6),
            "ratio",
            "supported rows retained",
        ),
        CellContextBetaFrontierMetric(
            "mean_uncertainty",
            round(fmean(uncertainty), 6),
            "bounded_score",
            "mean prior uncertainty",
        ),
        CellContextBetaFrontierMetric(
            "mean_candidate_count",
            round(fmean(candidates), 6),
            "candidates",
            "mean alternatives retained",
        ),
        CellContextBetaFrontierMetric(
            "ambiguity_control_count",
            float(sum(item.observed_state == "ambiguous" for item in evaluation.records)),
            "records",
            "ambiguous controls retained",
        ),
        CellContextBetaFrontierMetric(
            "domain_refusal_count",
            float(sum(item.observed_state == "out_of_domain" for item in evaluation.records)),
            "records",
            "domain-gated refusals retained",
        ),
    )
    return CellContextBetaFrontierMetrics(
        metrics, evaluation.accepted and all(item.value >= 0 for item in metrics)
    )


__all__ = [
    "CellContextBetaFrontierMetric",
    "CellContextBetaFrontierMetrics",
    "build_cell_context_beta_frontier_metrics",
]
