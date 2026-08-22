"""Review policy for topology-alpha controls and state boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierPolicyDecision:
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
class TopologyAlphaFrontierPolicyReport:
    decisions: tuple[TopologyAlphaFrontierPolicyDecision, ...]
    review_count: int
    publishable_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> TopologyAlphaFrontierPolicyDecision:
        for item in self.decisions:
            if item.record_id == record_id:
                return item
        raise KeyError(record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"decisions": [item.to_dict() for item in self.decisions], "review_count": self.review_count, "publishable_count": self.publishable_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_alpha_frontier_policy(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierPolicyReport:
    decisions = tuple(TopologyAlphaFrontierPolicyDecision(row.record_id, row.operation, row.observed_state, "review" if row.role == "control" or row.observed_state != "supported" or row.observed_issue_codes else "release_candidate", row.role == "control" or row.observed_state != "supported" or bool(row.observed_issue_codes), tuple(dict.fromkeys(("control_record" if row.role == "control" else "", "non_supported_state" if row.observed_state != "supported" else "", *row.observed_issue_codes))), "aggregate_research") for row in evaluation.rows)
    decisions = tuple(TopologyAlphaFrontierPolicyDecision(item.record_id, item.operation, item.state, item.disposition, item.review_required, tuple(reason for reason in item.reasons if reason), item.release_scope) for item in decisions)
    return TopologyAlphaFrontierPolicyReport(decisions, sum(item.review_required for item in decisions), sum(item.disposition == "release_candidate" for item in decisions), bool(decisions) and evaluation.accepted)


__all__ = ["TopologyAlphaFrontierPolicyDecision", "TopologyAlphaFrontierPolicyReport", "evaluate_topology_alpha_frontier_policy"]
