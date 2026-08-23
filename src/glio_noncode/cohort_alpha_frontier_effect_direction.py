"""Direction receipts for positive and contradictory cross-cohort paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierEffectDirectionRow:
    record_id: str
    operation: str
    declared_directions: tuple[str, ...]
    concordant: bool
    state: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierEffectDirectionReport:
    rows: tuple[CohortAlphaFrontierEffectDirectionRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def summarize_cohort_alpha_frontier_effect_direction(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierEffectDirectionReport:
    rows = []
    for row in evaluation.by_operation("C12"):
        directions = ("positive", "positive") if row.observed_state.value == "supported" else ("positive", "negative") if row.observed_state.value == "ambiguous" else ()
        rows.append(CohortAlphaFrontierEffectDirectionRow(row.record_id, row.operation, directions, len(set(directions)) <= 1 and bool(directions), row.observed_state.value, content_hash({"record_id": row.record_id, "directions": directions, "concordant": len(set(directions)) <= 1 and bool(directions), "state": row.observed_state.value}, prefix="alpha-effect-direction")))
    return CohortAlphaFrontierEffectDirectionReport(tuple(rows), len(rows) == 4 and sum(row.state == "ambiguous" for row in rows) == 1, content_hash(rows, prefix="alpha-effect-direction-report"))


__all__ = ["CohortAlphaFrontierEffectDirectionReport", "CohortAlphaFrontierEffectDirectionRow", "summarize_cohort_alpha_frontier_effect_direction"]
