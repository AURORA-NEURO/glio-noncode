"""Control-class coverage report for release readiness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierControlCoverageRow:
    operation: str
    state: str
    observed_count: int
    accepted_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierControlCoverage:
    rows: tuple[CohortBetaFrontierControlCoverageRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_control_coverage(evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierControlCoverage:
    rows = []
    for operation in ("C05", "C06", "C07", "C08"):
        for state in ("supported", "absent", "partial", "out_of_domain", "contradictory"):
            selected = tuple(item for item in evaluation.rows if item.operation == operation and item.observed_state.value == state)
            if selected:
                rows.append(CohortBetaFrontierControlCoverageRow(operation, state, len(selected), sum(item.accepted for item in selected), content_hash({"operation": operation, "state": state, "count": len(selected)}, prefix="control-coverage")))
    return CohortBetaFrontierControlCoverage(tuple(rows), len(rows) >= 12, content_hash(rows, prefix="control-coverage-report"))


__all__ = ["CohortBetaFrontierControlCoverage", "CohortBetaFrontierControlCoverageRow", "build_cohort_beta_frontier_control_coverage"]
