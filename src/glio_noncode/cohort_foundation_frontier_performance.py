"""Deterministic resource budgets for bounded aggregate execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_public_data import CohortFoundationOperation


@dataclass(frozen=True, slots=True)
class CohortFoundationPerformanceBudget:
    operation: CohortFoundationOperation
    maximum_records: int
    maximum_candidates: int
    expected_complexity: str
    memory_class: str
    within_fixture: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationPerformanceReport:
    report_id: str
    budgets: tuple[CohortFoundationPerformanceBudget, ...]
    total_records: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_performance_report(evaluation: CohortFoundationEvaluation) -> CohortFoundationPerformanceReport:
    definitions = {
        CohortFoundationOperation.COHORT_QUERY: (64, 256, "linear-selection", "bounded"),
        CohortFoundationOperation.BACKGROUND_RATE: (256, 64, "interval-reduction", "bounded"),
        CohortFoundationOperation.SEQUENCE_CONTROL: (256, 256, "candidate-sort", "bounded"),
        CohortFoundationOperation.CHROMATIN_CONTROL: (256, 256, "feature-distance-sort", "bounded"),
    }
    budgets = []
    for operation in CohortFoundationOperation:
        maximum_records, maximum_candidates, complexity, memory_class = definitions[operation]
        observed = sum(1 for item in evaluation.executions if item.operation is operation)
        body = {"operation": operation, "records": maximum_records, "candidates": maximum_candidates, "complexity": complexity, "memory": memory_class}
        budgets.append(CohortFoundationPerformanceBudget(operation, maximum_records, maximum_candidates, complexity, memory_class, observed <= maximum_records, content_hash(body)))
    body = {"report_id": "cohort-foundation-frontier-performance", "budgets": budgets, "total": len(evaluation.executions)}
    return CohortFoundationPerformanceReport(body["report_id"], tuple(budgets), len(evaluation.executions), all(item.within_fixture for item in budgets), content_hash(body))


__all__ = ["CohortFoundationPerformanceBudget", "CohortFoundationPerformanceReport", "build_cohort_foundation_frontier_performance_report"]
