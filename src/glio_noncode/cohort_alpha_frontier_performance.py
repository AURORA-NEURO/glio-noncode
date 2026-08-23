"""Deterministic performance budgets for the aggregate alpha pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPerformanceBudget:
    budget_id: str
    operation: str
    rows: int
    max_units: int
    max_memory_units: int
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPerformanceMeasurement:
    budget_id: str
    observed_units: int
    observed_memory_units: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPerformanceReport:
    budgets: tuple[CohortAlphaFrontierPerformanceBudget, ...]
    measurements: tuple[CohortAlphaFrontierPerformanceMeasurement, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_alpha_frontier_performance_budgets() -> tuple[CohortAlphaFrontierPerformanceBudget, ...]:
    raw = (("C09", 4, 96, 64), ("C10", 4, 96, 64), ("C11", 4, 96, 64), ("C12", 4, 128, 80), ("ALL", 16, 512, 256))
    return tuple(CohortAlphaFrontierPerformanceBudget(f"alpha-perf-{operation.lower()}", operation, rows, units, memory, "bounded deterministic fixture budget", content_hash({"operation": operation, "rows": rows, "units": units, "memory": memory}, prefix="alpha-perf-budget")) for operation, rows, units, memory in raw)


def measure_cohort_alpha_frontier_performance(evaluation: CohortAlphaFrontierEvaluation, budgets: tuple[CohortAlphaFrontierPerformanceBudget, ...] | None = None) -> CohortAlphaFrontierPerformanceReport:
    selected = budgets or default_cohort_alpha_frontier_performance_budgets()
    measurements = []
    for budget in selected:
        rows = len(evaluation.rows) if budget.operation == "ALL" else len(evaluation.by_operation(budget.operation))
        units = rows * (24 if budget.operation == "C12" else 16)
        memory = rows * 8
        accepted = rows == budget.rows and units <= budget.max_units and memory <= budget.max_memory_units
        measurements.append(CohortAlphaFrontierPerformanceMeasurement(budget.budget_id, units, memory, accepted, content_hash({"budget": budget.budget_id, "units": units, "memory": memory, "accepted": accepted}, prefix="alpha-perf")))
    values = tuple(measurements)
    return CohortAlphaFrontierPerformanceReport(tuple(selected), values, all(item.accepted for item in values), content_hash(values, prefix="alpha-performance"))


__all__ = ["CohortAlphaFrontierPerformanceBudget", "CohortAlphaFrontierPerformanceMeasurement", "CohortAlphaFrontierPerformanceReport", "default_cohort_alpha_frontier_performance_budgets", "measure_cohort_alpha_frontier_performance"]
