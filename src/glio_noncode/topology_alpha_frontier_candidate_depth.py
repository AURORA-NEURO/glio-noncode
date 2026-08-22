"""Candidate and alternative retention for alpha controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierCandidateObservation:
    record_id: str
    operation: str
    candidate_kind: str
    state: str
    retained: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierCandidateDepthReport:
    observations: tuple[TopologyAlphaFrontierCandidateObservation, ...]
    candidate_count: int
    retained_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyAlphaFrontierCandidateObservation, ...]:
        return tuple(item for item in self.observations if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"observations": [item.to_dict() for item in self.observations], "candidate_count": self.candidate_count, "retained_count": self.retained_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_alpha_frontier_candidates(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierCandidateDepthReport:
    values = tuple(TopologyAlphaFrontierCandidateObservation(row.record_id, row.operation, "measured_result" if row.observed_state == "supported" else "review_candidate", row.observed_state, bool(row.adapter.evidence_ids) or row.observed_state in {"partial", "ambiguous", "out_of_domain"}, "retains primitive output, missingness, or context boundary") for row in evaluation.rows)
    return TopologyAlphaFrontierCandidateDepthReport(values, len(values), sum(item.retained for item in values), bool(values) and all(item.retained for item in values))


__all__ = ["TopologyAlphaFrontierCandidateDepthReport", "TopologyAlphaFrontierCandidateObservation", "audit_topology_alpha_frontier_candidates"]
