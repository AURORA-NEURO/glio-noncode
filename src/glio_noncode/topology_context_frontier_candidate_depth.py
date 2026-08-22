"""Candidate retention checks for contacts and boundary clusters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierCandidateObservation:
    record_id: str
    operation: str
    candidate_count: int
    selected_count: int
    ambiguity_preserved: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierCandidateDepthReport:
    observations: tuple[TopologyContextFrontierCandidateObservation, ...]
    candidate_count: int
    ambiguity_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "observations": [item.to_dict() for item in self.observations],
            "candidate_count": self.candidate_count,
            "ambiguity_count": self.ambiguity_count,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_context_frontier_candidates(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierCandidateDepthReport:
    observations = tuple(
        TopologyContextFrontierCandidateObservation(
            item.record_id,
            item.operation,
            len(item.adapter.measurements.get("interaction_ids", ()))
            + int(item.adapter.measurements.get("cluster_count", 0)),
            int(item.observed_state == "supported"),
            item.observed_state == "ambiguous"
            or bool(item.adapter.measurements.get("cluster_count", 0) > 1),
        )
        for item in evaluation.rows
    )
    candidate_count = sum(item.candidate_count for item in observations)
    ambiguity_count = sum(item.ambiguity_preserved for item in observations)
    return TopologyContextFrontierCandidateDepthReport(
        observations, candidate_count, ambiguity_count, candidate_count >= 8
    )


__all__ = [
    "TopologyContextFrontierCandidateDepthReport",
    "TopologyContextFrontierCandidateObservation",
    "audit_topology_context_frontier_candidates",
]
