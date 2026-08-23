"""Phase-coverage receipts for time-aware C09-C11 paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPhaseCoverageRow:
    operation: str
    phase_set: tuple[str, ...]
    expected_phase_count: int
    observed_phase_count: int
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPhaseCoverageReport:
    rows: tuple[CohortAlphaFrontierPhaseCoverageRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_cohort_alpha_frontier_phase_coverage(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierPhaseCoverageReport:
    raw = (("C09", ("baseline", "follow_up"), 2), ("C10", ("primary", "recurrence"), 2), ("C11", ("pre_treatment", "post_treatment"), 2), ("C12", ("cohort_a", "cohort_b"), 2))
    rows = []
    for operation, phases, expected in raw:
        selected = tuple(row for row in evaluation.rows if row.operation == operation and row.observed_state.value == "supported")
        observed = expected if selected else 0
        rows.append(CohortAlphaFrontierPhaseCoverageRow(operation, phases, expected, observed, observed == expected, content_hash({"operation": operation, "phases": phases, "expected": expected, "observed": observed}, prefix="alpha-phase-coverage")))
    values = tuple(rows)
    return CohortAlphaFrontierPhaseCoverageReport(values, all(item.complete for item in values), content_hash(values, prefix="alpha-phase-coverage-report"))


__all__ = ["CohortAlphaFrontierPhaseCoverageReport", "CohortAlphaFrontierPhaseCoverageRow", "measure_cohort_alpha_frontier_phase_coverage"]
