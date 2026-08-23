"""Detailed explanations for every non-supported state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierBoundaryExplanation:
    record_id: str
    operation: str
    state: str
    trigger: str
    next_evidence: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierBoundaryExplanationSet:
    explanations: tuple[CohortAlphaFrontierBoundaryExplanation, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_boundary_explanations(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierBoundaryExplanationSet:
    triggers = {"partial": ("missing channel", ("required quantitative field", "phase receipt")), "ambiguous": ("direction disagreement", ("cohort concordance", "independent replication")), "out_of_domain": ("context mismatch", ("target context receipt",)), "abstained": ("empty observation set", ("source observation",))}
    values = tuple(CohortAlphaFrontierBoundaryExplanation(row.record_id, row.operation, row.observed_state.value, triggers[row.observed_state.value][0], triggers[row.observed_state.value][1], content_hash({"record_id": row.record_id, "operation": row.operation, "state": row.observed_state.value, "trigger": triggers[row.observed_state.value][0], "next": triggers[row.observed_state.value][1]}, prefix="alpha-boundary-explanation")) for row in evaluation.rows if row.observed_state.value != "supported")
    return CohortAlphaFrontierBoundaryExplanationSet(values, len(values) == 12 and all(item.next_evidence for item in values), content_hash(values, prefix="alpha-boundary-explanations"))


__all__ = ["CohortAlphaFrontierBoundaryExplanation", "CohortAlphaFrontierBoundaryExplanationSet", "build_cohort_alpha_frontier_boundary_explanations"]
