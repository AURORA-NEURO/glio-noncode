"""Operational metrics for Domain 09 public aggregate execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierMetric:
    metric_id: str
    operation: str
    value: float
    denominator: int
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierMetrics:
    metrics: tuple[TopologyContextFrontierMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def get(self, metric_id: str) -> TopologyContextFrontierMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"metrics": [item.to_dict() for item in self.metrics], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_metrics(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierMetrics:
    total = len(evaluation.rows)
    metrics = (
        TopologyContextFrontierMetric(
            "record_count", "all", float(total), total, "fixture rows evaluated"
        ),
        TopologyContextFrontierMetric(
            "state_match_rate",
            "all",
            round(evaluation.state_match_count / total, 9) if total else 0.0,
            total,
            "expected states matched",
        ),
        TopologyContextFrontierMetric(
            "issue_match_rate",
            "all",
            round(evaluation.issue_match_count / total, 9) if total else 0.0,
            total,
            "expected issue floors matched",
        ),
        TopologyContextFrontierMetric(
            "contact_rows",
            "contact_import",
            float(
                sum(
                    len(item.adapter.measurements.get("interaction_ids", ()))
                    for item in evaluation.by_operation("contact_import")
                )
            ),
            total,
            "returned contact evidence rows",
        ),
        TopologyContextFrontierMetric(
            "boundary_clusters",
            "boundary_ensemble",
            float(
                sum(
                    item.adapter.measurements.get("cluster_count", 0)
                    for item in evaluation.by_operation("boundary_ensemble")
                )
            ),
            total,
            "retained boundary alternatives",
        ),
        TopologyContextFrontierMetric(
            "insulation_deltas",
            "insulation_delta",
            float(
                sum(
                    item.adapter.measurements.get("delta") is not None
                    for item in evaluation.by_operation("insulation_delta")
                )
            ),
            total,
            "nonmissing insulation comparisons",
        ),
    )
    return TopologyContextFrontierMetrics(metrics=metrics, accepted=evaluation.accepted)


__all__ = [
    "TopologyContextFrontierMetric",
    "TopologyContextFrontierMetrics",
    "build_topology_context_frontier_metrics",
]
