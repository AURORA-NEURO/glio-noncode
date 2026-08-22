"""Candidate count and alternative accounting for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierCandidateObservation:
    record_id: str
    operation: str
    state: str
    candidate_count: int
    evidence_count: int
    alternative_count: int
    issue_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierCandidateDepthReport:
    observations: tuple[LinkGraphFoundationFrontierCandidateObservation, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"observations": [item.to_dict() for item in self.observations], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_link_graph_foundation_frontier_candidates(evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierCandidateDepthReport:
    observations = tuple(LinkGraphFoundationFrontierCandidateObservation(row.record_id, row.operation, row.observed_state, int(row.adapter.measurements.get("link_count", row.adapter.measurements.get("element_count", 0))), len(row.adapter.evidence_ids), len(row.adapter.measurements.get("alternative_genes", ())), row.observed_issue_codes) for row in evaluation.rows)
    checks = (check("rows", len(observations) == len(evaluation.rows), "candidate rows align"), check("alternatives", any(item.alternative_count for item in observations) or any(item.state == "ambiguous" for item in observations), "ambiguity is represented"), check("issues", all(item.issue_codes or item.state == "supported" for item in observations), "non-clean candidates carry issues"))
    return LinkGraphFoundationFrontierCandidateDepthReport(observations, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierCandidateDepthReport", "LinkGraphFoundationFrontierCandidateObservation", "audit_link_graph_foundation_frontier_candidates"]
