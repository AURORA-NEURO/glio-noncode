"""Release scorecard with transparent denominators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_metrics import LinkGraphAlphaFrontierMetrics
from .link_graph_alpha_frontier_quality_gate import LinkGraphAlphaFrontierQualityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierScore:
    score_id: str
    numerator: int
    denominator: int
    value: float
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierScorecard:
    scores: tuple[LinkGraphAlphaFrontierScore, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def score(self, score_id: str) -> LinkGraphAlphaFrontierScore:
        for item in self.scores:
            if item.score_id == score_id:
                return item
        raise KeyError(score_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"scores": [item.to_dict() for item in self.scores], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_scorecard(metrics: LinkGraphAlphaFrontierMetrics, quality: LinkGraphAlphaFrontierQualityReport) -> LinkGraphAlphaFrontierScorecard:
    total = metrics.record_count
    scores = (LinkGraphAlphaFrontierScore("state_accuracy", sum(item.state_match_count for item in metrics.operations), total, metrics.state_accuracy, "state replay agreement"), LinkGraphAlphaFrontierScore("issue_accuracy", sum(item.issue_match_count for item in metrics.operations), total, metrics.issue_accuracy, "issue control agreement"), LinkGraphAlphaFrontierScore("quality_floor", sum(item.passed for item in quality.checks), len(quality.checks), sum(item.passed for item in quality.checks) / len(quality.checks) if quality.checks else 0.0, "quality checks passed"))
    return LinkGraphAlphaFrontierScorecard(scores, all(item.value == 1.0 for item in scores))


__all__ = ["LinkGraphAlphaFrontierScore", "LinkGraphAlphaFrontierScorecard", "build_link_graph_alpha_frontier_scorecard"]
