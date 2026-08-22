"""Candidate and territory label depth summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierCandidateObservation:
    operation: str
    record_id: str
    candidate_id: str
    score: float | None
    margin: float | None
    result_state: str
    retained: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierCandidateDepthReport:
    candidates: tuple[CellContextAlphaFrontierCandidateObservation, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"candidate_count": self.candidate_count}


def audit_cell_context_alpha_frontier_candidates(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierCandidateDepthReport:
    candidates = []
    for row in evaluation.records:
        for result in row.adapter.measurements.get("results", ()):
            if not isinstance(result, dict):
                continue
            candidate_id = str(
                result.get(
                    "niche_id",
                    result.get(
                        "phase", result.get("state_id", result.get("territory_label", "unknown"))
                    ),
                )
            )
            score = result.get(
                "median_support", result.get("core_score", result.get("baseline_support"))
            )
            margin = result.get(
                "score_margin_to_next",
                result.get(
                    "phase_margin_to_next",
                    result.get("core_margin_delta", result.get("support_delta")),
                ),
            )
            candidates.append(
                CellContextAlphaFrontierCandidateObservation(
                    row.operation,
                    row.record_id,
                    candidate_id,
                    None if score is None else float(score),
                    None if margin is None else float(margin),
                    str(result.get("state", row.observed_state)),
                    True,
                )
            )
    return CellContextAlphaFrontierCandidateDepthReport(
        tuple(candidates),
        bool(candidates) and all(item.score is None or 0 <= item.score <= 1 for item in candidates),
    )


__all__ = [
    "CellContextAlphaFrontierCandidateDepthReport",
    "CellContextAlphaFrontierCandidateObservation",
    "audit_cell_context_alpha_frontier_candidates",
]
