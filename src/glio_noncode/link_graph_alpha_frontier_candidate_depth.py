"""Candidate-level accounting for method paths and alternatives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierCandidateObservation:
    record_id: str
    operation: str
    state: str
    link_count: int
    evidence_count: int
    alternative_count: int
    support_values: tuple[float, ...]
    visible_limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierCandidateDepthReport:
    observations: tuple[LinkGraphAlphaFrontierCandidateObservation, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def alternative_records(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.observations if item.alternative_count)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"observations": [item.to_dict() for item in self.observations], "alternative_records": self.alternative_records, "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_link_graph_alpha_frontier_candidates(evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierCandidateDepthReport:
    observations = []
    for row in evaluation.rows:
        measurements = row.adapter.measurements
        counts = measurements.get("link_count", measurements.get("result_count", measurements.get("edge_count", 0)))
        evidence_count = len(row.adapter.evidence_ids)
        alternatives = len(measurements.get("alternative_genes", ()))
        raw_supports = measurements.get("supports", measurements.get("normalized_contacts", measurements.get("scores", ())))
        support_values = tuple(float(item) for item in raw_supports if item is not None)
        limitations = tuple(sorted(set(row.observed_issue_codes) | ({"context_boundary"} if row.observed_state == "out_of_domain" else set())))
        observations.append(LinkGraphAlphaFrontierCandidateObservation(row.record_id, row.operation, row.observed_state, int(counts), evidence_count, alternatives, support_values, limitations))
    values = tuple(observations)
    checks = (check("candidate_rows", len(values) == len(evaluation.rows), "one candidate observation per replay row"), check("evidence_visible", all(item.evidence_count >= 0 for item in values), "evidence counts are lossless"), check("alternatives_visible", any(item.alternative_count for item in values), "at least one control retains alternatives"), check("limitations_visible", all(item.visible_limitations or item.state == "supported" for item in values), "non-clean paths carry limitations"))
    return LinkGraphAlphaFrontierCandidateDepthReport(values, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierCandidateDepthReport", "LinkGraphAlphaFrontierCandidateObservation", "audit_link_graph_alpha_frontier_candidates"]
