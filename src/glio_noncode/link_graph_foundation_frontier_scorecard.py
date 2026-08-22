"""Transparent release scorecard for baseline replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_metrics import LinkGraphFoundationFrontierMetrics
from .link_graph_foundation_frontier_quality_gate import LinkGraphFoundationFrontierQualityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierScore:
    score_id: str
    numerator: int
    denominator: int
    value: float
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierScorecard:
    scores: tuple[LinkGraphFoundationFrontierScore, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"scores": [item.to_dict() for item in self.scores], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_scorecard(metrics: LinkGraphFoundationFrontierMetrics, quality: LinkGraphFoundationFrontierQualityReport) -> LinkGraphFoundationFrontierScorecard:
    total = metrics.record_count
    scores = (LinkGraphFoundationFrontierScore("state_accuracy", int(metrics.state_accuracy * total), total, metrics.state_accuracy, "state replay agreement"), LinkGraphFoundationFrontierScore("quality", sum(item.passed for item in quality.checks), len(quality.checks), sum(item.passed for item in quality.checks) / len(quality.checks), "quality checks passed"))
    return LinkGraphFoundationFrontierScorecard(scores, all(item.value == 1.0 for item in scores))


__all__ = ["LinkGraphFoundationFrontierScore", "LinkGraphFoundationFrontierScorecard", "build_link_graph_foundation_frontier_scorecard"]
