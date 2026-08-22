"""Publication policy for topology context evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierPolicyDecision:
    record_id: str
    decision: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierPolicyReport:
    decisions: tuple[TopologyContextFrontierPolicyDecision, ...]
    accepted: bool
    review_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "decisions": [item.to_dict() for item in self.decisions],
            "accepted": self.accepted,
            "review_count": self.review_count,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_context_frontier_policy(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierPolicyReport:
    decisions = tuple(
        TopologyContextFrontierPolicyDecision(
            item.record_id,
            "accept" if item.observed_state == "supported" else "review",
            () if item.observed_state == "supported" else (f"state:{item.observed_state}",),
        )
        for item in evaluation.rows
    )
    review_count = sum(item.decision == "review" for item in decisions)
    return TopologyContextFrontierPolicyReport(decisions, evaluation.accepted, review_count)


__all__ = [
    "TopologyContextFrontierPolicyDecision",
    "TopologyContextFrontierPolicyReport",
    "evaluate_topology_context_frontier_policy",
]
