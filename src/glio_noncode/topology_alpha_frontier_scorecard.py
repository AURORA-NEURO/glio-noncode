"""Operation scorecards for compact release and review dashboards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierScorecard:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    supported_count: int
    partial_count: int
    ambiguous_count: int
    foreign_count: int
    state_match_rate: float
    issue_match_rate: float
    address_closure_rate: float
    evidence_closure_rate: float
    review_required: bool
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierScorecardReport:
    cards: tuple[TopologyAlphaFrontierScorecard, ...]
    aggregate_record_count: int
    aggregate_supported_count: int
    aggregate_review_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> TopologyAlphaFrontierScorecard:
        for item in self.cards:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cards": [item.to_dict() for item in self.cards], "aggregate_record_count": self.aggregate_record_count, "aggregate_supported_count": self.aggregate_supported_count, "aggregate_review_count": self.aggregate_review_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_scorecards(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierScorecardReport:
    cards = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = evaluation.by_operation(operation)
        denominator = len(rows)
        cards.append(TopologyAlphaFrontierScorecard(operation, denominator, sum(item.role == "positive" for item in rows), sum(item.role == "control" for item in rows), sum(item.observed_state == "supported" for item in rows), sum(item.observed_state == "partial" for item in rows), sum(item.observed_state == "ambiguous" for item in rows), sum(item.observed_state == "out_of_domain" for item in rows), sum(item.state_match for item in rows) / denominator, sum(item.issue_match for item in rows) / denominator, sum(item.adapter.content_address.startswith("sha256:") for item in rows) / denominator, sum(bool(item.adapter.evidence_ids) for item in rows) / denominator, any(item.role == "control" for item in rows), "descriptive aggregate output with explicit review controls"))
    values = tuple(cards)
    return TopologyAlphaFrontierScorecardReport(values, sum(item.record_count for item in values), sum(item.supported_count for item in values), sum(item.control_count for item in values), len(values) == 4 and all(item.state_match_rate == 1.0 and item.issue_match_rate == 1.0 and item.address_closure_rate == 1.0 for item in values))


def summarize_topology_alpha_frontier_scorecards(report: TopologyAlphaFrontierScorecardReport) -> dict[str, Any]:
    return {"operations": [item.operation for item in report.cards], "record_count": report.aggregate_record_count, "supported_count": report.aggregate_supported_count, "review_count": report.aggregate_review_count, "accepted": report.accepted}


__all__ = ["TopologyAlphaFrontierScorecard", "TopologyAlphaFrontierScorecardReport", "build_topology_alpha_frontier_scorecards", "summarize_topology_alpha_frontier_scorecards"]
