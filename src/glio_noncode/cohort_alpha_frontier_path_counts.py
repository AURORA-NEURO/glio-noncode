"""Path counts used as a small independent fixture oracle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPathCounts:
    operation_counts: dict[str, int]
    accepted_counts: dict[str, int]
    state_counts: dict[str, int]
    total: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def count_cohort_alpha_frontier_paths(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierPathCounts:
    operation_counts = {operation: sum(row.operation == operation for row in evaluation.rows) for operation in ("C09", "C10", "C11", "C12")}
    accepted_counts = {operation: sum(row.operation == operation and row.accepted for row in evaluation.rows) for operation in operation_counts}
    state_counts = {state: sum(row.observed_state.value == state for row in evaluation.rows) for state in ("supported", "partial", "ambiguous", "out_of_domain", "abstained")}
    body = {"operations": operation_counts, "accepted": accepted_counts, "states": state_counts, "total": len(evaluation.rows)}
    return CohortAlphaFrontierPathCounts(operation_counts, accepted_counts, state_counts, len(evaluation.rows), evaluation.accepted and all(value == 4 for value in operation_counts.values()) and sum(state_counts.values()) == 16, content_hash(body, prefix="alpha-path-counts"))


__all__ = ["CohortAlphaFrontierPathCounts", "count_cohort_alpha_frontier_paths"]
