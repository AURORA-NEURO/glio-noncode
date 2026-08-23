"""State count assertions with explicit control expectation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierStateCounts:
    supported: int
    partial: int
    ambiguous: int
    out_of_domain: int
    abstained: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def count_cohort_alpha_frontier_states(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierStateCounts:
    values = {state: sum(row.observed_state.value == state for row in evaluation.rows) for state in ("supported", "partial", "ambiguous", "out_of_domain", "abstained")}
    body = {**values, "total": sum(values.values())}
    return CohortAlphaFrontierStateCounts(values["supported"], values["partial"], values["ambiguous"], values["out_of_domain"], values["abstained"], evaluation.accepted and body["total"] == 16 and values["supported"] == 4 and values["out_of_domain"] == 4 and values["abstained"] == 4, content_hash(body, prefix="alpha-state-counts"))


__all__ = ["CohortAlphaFrontierStateCounts", "count_cohort_alpha_frontier_states"]
