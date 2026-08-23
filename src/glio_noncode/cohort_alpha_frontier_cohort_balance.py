"""Cohort balance receipts for the replication operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCohortBalanceRow:
    record_id: str
    cohort_ids: tuple[str, ...]
    sample_counts: tuple[int, ...]
    minimum_sample_count: int
    balanced: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCohortBalanceReport:
    rows: tuple[CohortAlphaFrontierCohortBalanceRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_cohort_alpha_frontier_cohort_balance(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierCohortBalanceReport:
    rows = []
    for row in evaluation.by_operation("C12"):
        observations = row.result.get("observations", ())
        cohorts = tuple(str(item.get("cohort_id", "")) for item in observations if isinstance(item, dict))
        counts = tuple(int(item.get("sample_count", 0)) for item in observations if isinstance(item, dict))
        minimum = min(counts) if counts else 0
        rows.append(CohortAlphaFrontierCohortBalanceRow(row.record_id, cohorts, counts, minimum, bool(cohorts) and min(counts) >= 10, content_hash({"record_id": row.record_id, "cohorts": cohorts, "counts": counts, "minimum": minimum}, prefix="alpha-cohort-balance")))
    return CohortAlphaFrontierCohortBalanceReport(tuple(rows), len(rows) == 4 and sum(row.balanced for row in rows) >= 1, content_hash(rows, prefix="alpha-cohort-balance-report"))


__all__ = ["CohortAlphaFrontierCohortBalanceReport", "CohortAlphaFrontierCohortBalanceRow", "measure_cohort_alpha_frontier_cohort_balance"]
