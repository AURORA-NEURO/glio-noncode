"""Result digest with state totals and deterministic evaluation address."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierResultDigest:
    evaluation_address: str
    total_rows: int
    accepted_rows: int
    state_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_result_digest(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierResultDigest:
    states = {state: sum(row.observed_state.value == state for row in evaluation.rows) for state in ("supported", "partial", "ambiguous", "out_of_domain", "abstained")}
    body = {"evaluation": evaluation.content_address, "total": len(evaluation.rows), "accepted": sum(row.accepted for row in evaluation.rows), "states": states}
    return CohortAlphaFrontierResultDigest(body["evaluation"], body["total"], body["accepted"], states, evaluation.accepted and sum(states.values()) == 16, content_hash(body, prefix="alpha-result-digest"))


__all__ = ["CohortAlphaFrontierResultDigest", "build_cohort_alpha_frontier_result_digest"]
