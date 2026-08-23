"""Sample coverage receipts independent of result-state classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSampleCoverageRow:
    operation: str
    expected_rows: int
    observed_rows: int
    source_backed_rows: int
    coverage_percent: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSampleCoverageReport:
    rows: tuple[CohortAlphaFrontierSampleCoverageRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_cohort_alpha_frontier_sample_coverage(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierSampleCoverageReport:
    rows = []
    for operation in ("C09", "C10", "C11", "C12"):
        selected = tuple(row for row in evaluation.rows if row.operation == operation)
        observed = len(selected)
        coverage = round(100 * observed / 4, 2)
        rows.append(CohortAlphaFrontierSampleCoverageRow(operation, 4, observed, sum(bool(row.result) for row in selected), coverage, observed == 4 and coverage == 100.0, content_hash({"operation": operation, "expected": 4, "observed": observed, "coverage": coverage}, prefix="alpha-sample-coverage")))
    values = tuple(rows)
    return CohortAlphaFrontierSampleCoverageReport(values, all(item.accepted for item in values), content_hash(values, prefix="alpha-sample-coverage-report"))


__all__ = ["CohortAlphaFrontierSampleCoverageReport", "CohortAlphaFrontierSampleCoverageRow", "measure_cohort_alpha_frontier_sample_coverage"]
