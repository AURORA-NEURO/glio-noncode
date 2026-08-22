"""Review and publication policy for evidence states and controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierPolicyDecision:
    record_id: str
    operation: str
    state: str
    disposition: str
    review_required: bool
    reasons: tuple[str, ...]
    release_scope: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierPolicyReport:
    decisions: tuple[TopologyBetaFrontierPolicyDecision, ...]
    review_count: int
    publishable_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> TopologyBetaFrontierPolicyDecision:
        for item in self.decisions:
            if item.record_id == record_id:
                return item
        raise KeyError(record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"decisions": [item.to_dict() for item in self.decisions], "review_count": self.review_count, "publishable_count": self.publishable_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_beta_frontier_policy(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierPolicyReport:
    decisions = []
    for row in evaluation.rows:
        review = row.role == "control" or row.observed_state != "supported" or bool(row.observed_issue_codes)
        reasons = tuple(dict.fromkeys(("control_record" if row.role == "control" else "", "non_supported_state" if row.observed_state != "supported" else "", *row.observed_issue_codes)))
        reasons = tuple(item for item in reasons if item)
        decisions.append(TopologyBetaFrontierPolicyDecision(row.record_id, row.operation, row.observed_state, "review" if review else "release_candidate", review, reasons, "aggregate_research"))
    values = tuple(decisions)
    return TopologyBetaFrontierPolicyReport(values, sum(item.review_required for item in values), sum(item.disposition == "release_candidate" for item in values), bool(values) and evaluation.accepted)


__all__ = ["TopologyBetaFrontierPolicyDecision", "TopologyBetaFrontierPolicyReport", "evaluate_topology_beta_frontier_policy"]
