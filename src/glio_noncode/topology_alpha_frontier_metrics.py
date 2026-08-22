"""Stable state and review metrics for topology-alpha replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierMetric:
    name: str
    value: float
    numerator: int
    denominator: int
    unit: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierMetrics:
    metrics: tuple[TopologyAlphaFrontierMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def get(self, name: str) -> TopologyAlphaFrontierMetric:
        for item in self.metrics:
            if item.name == name:
                return item
        raise KeyError(name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"metrics": [item.to_dict() for item in self.metrics], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _ratio(name: str, numerator: int, denominator: int, detail: str) -> TopologyAlphaFrontierMetric:
    return TopologyAlphaFrontierMetric(name, numerator / denominator if denominator else 0.0, numerator, denominator, "ratio", detail)


def build_topology_alpha_frontier_metrics(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierMetrics:
    total = len(evaluation.rows)
    states = {state: sum(item.observed_state == state for item in evaluation.rows) for state in ("supported", "partial", "ambiguous", "abstained", "invalid", "out_of_domain", "contradictory")}
    metrics = (TopologyAlphaFrontierMetric("record_count", float(total), total, total, "records", "records replayed"), _ratio("state_match_rate", evaluation.state_match_count, total, "expected states matched"), _ratio("issue_match_rate", evaluation.issue_match_count, total, "expected issue floors matched"), _ratio("positive_support_rate", sum(item.observed_state == "supported" for item in evaluation.positives()), len(evaluation.positives()), "positive records retaining support"), _ratio("control_review_rate", len(evaluation.controls()), total, "controls visible for review"), *(TopologyAlphaFrontierMetric(f"state_{key}_count", float(value), value, total, "records", f"records in {key} state") for key, value in states.items()), _ratio("address_closure_rate", sum(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows), total, "result addresses present"))
    return TopologyAlphaFrontierMetrics(metrics, bool(metrics) and evaluation.accepted)


__all__ = ["TopologyAlphaFrontierMetric", "TopologyAlphaFrontierMetrics", "build_topology_alpha_frontier_metrics"]
