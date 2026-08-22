"""Candidate-level summaries that keep alternatives and evidence counts visible."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierCandidateObservation:
    operation: str
    record_id: str
    candidate_id: str
    support_score: float
    uncertainty: float
    evidence_count: int
    retained: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierCandidateDepthReport:
    candidates: tuple[CellContextBetaFrontierCandidateObservation, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.candidates:
            raise ValueError("beta candidate depth is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"candidate_count": self.candidate_count}


def audit_cell_context_beta_frontier_candidates(
    evaluation: CellContextBetaFrontierEvaluation,
) -> CellContextBetaFrontierCandidateDepthReport:
    candidates = []
    for row in evaluation.records:
        support = row.adapter.measurements.get("candidate_support", {})
        uncertainty = row.adapter.measurements.get("candidate_uncertainty", {})
        counts = row.adapter.measurements.get("candidate_evidence_counts", {})
        for candidate_id in row.adapter.measurements.get("candidate_ids", ()):
            candidates.append(
                CellContextBetaFrontierCandidateObservation(
                    row.operation,
                    row.record_id,
                    candidate_id,
                    float(support.get(candidate_id, 0.0)),
                    float(uncertainty.get(candidate_id, 1.0)),
                    int(counts.get(candidate_id, 0)),
                    True,
                )
            )
    return CellContextBetaFrontierCandidateDepthReport(
        tuple(candidates),
        all(0 <= item.support_score <= 1 and 0 <= item.uncertainty <= 1 for item in candidates),
    )


__all__ = [
    "CellContextBetaFrontierCandidateDepthReport",
    "CellContextBetaFrontierCandidateObservation",
    "audit_cell_context_beta_frontier_candidates",
]
