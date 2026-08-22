"""Stable operational metrics for the C05-C08 fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierMetric:
    name: str
    value: float
    numerator: int
    denominator: int
    unit: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierMetrics:
    metrics: tuple[TopologyBetaFrontierMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def get(self, name: str) -> TopologyBetaFrontierMetric:
        for item in self.metrics:
            if item.name == name:
                return item
        raise KeyError(name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"metrics": [item.to_dict() for item in self.metrics], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _metric(name: str, numerator: int, denominator: int, detail: str) -> TopologyBetaFrontierMetric:
    return TopologyBetaFrontierMetric(name, numerator / denominator if denominator else 0.0, numerator, denominator, "ratio", detail)


def build_topology_beta_frontier_metrics(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierMetrics:
    total = len(evaluation.rows)
    by_state = {state: sum(item.observed_state == state for item in evaluation.rows) for state in ("supported", "partial", "ambiguous", "absent", "abstained", "out_of_domain")}
    metrics = (
        TopologyBetaFrontierMetric("record_count", float(total), total, total, "records", "records replayed"),
        _metric("state_match_rate", evaluation.state_match_count, total, "expected states matched"),
        _metric("issue_match_rate", evaluation.issue_match_count, total, "expected issue floors matched"),
        _metric("positive_support_rate", sum(item.observed_state == "supported" for item in evaluation.positives()), len(evaluation.positives()), "positive records retaining support"),
        _metric("control_review_rate", len(evaluation.controls()), total, "controls retained for review"),
        *(TopologyBetaFrontierMetric(f"state_{key}_count", float(value), value, total, "records", f"records observed in {key} state") for key, value in by_state.items()),
        _metric("address_closure_rate", sum(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows), total, "adapter content addresses present"),
    )
    return TopologyBetaFrontierMetrics(metrics, bool(metrics and evaluation.accepted))


__all__ = ["TopologyBetaFrontierMetric", "TopologyBetaFrontierMetrics", "build_topology_beta_frontier_metrics"]
