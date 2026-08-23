"""Bounded performance receipts for the deterministic fixture rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierPerformanceReport:
    row_count: int
    estimated_operations: int
    max_rows_per_operation: int
    memory_budget_rows: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_performance_report(evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierPerformanceReport:
    counts = [sum(item.operation == operation for item in evaluation.rows) for operation in ("C05", "C06", "C07", "C08")]
    body = {"row_count": len(evaluation.rows), "estimated_operations": sum(counts), "max_rows": max(counts, default=0), "memory_budget": 1024}
    return CohortBetaFrontierPerformanceReport(len(evaluation.rows), sum(counts), max(counts, default=0), 1024, len(evaluation.rows) <= 1024 and sum(counts) == len(evaluation.rows), content_hash(body, prefix="performance"))


__all__ = ["CohortBetaFrontierPerformanceReport", "build_cohort_beta_frontier_performance_report"]
