"""Benchmark-style workload receipts without external timing dependence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierBenchmarkCase:
    case_id: str
    operation: str
    input_rows: int
    expected_result_rows: int
    max_work_units: int
    observed_work_units: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierBenchmarkReport:
    cases: tuple[CohortBetaFrontierBenchmarkCase, ...]
    total_work_units: int
    max_work_units: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _case(operation: str, fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierBenchmarkCase:
    input_rows = sum(1 for record in fixture.records if record.operation == operation)
    result_rows = sum(1 for row in evaluation.rows if row.operation == operation)
    observed = input_rows * input_rows + result_rows * 3
    maximum = 256
    body = {"operation": operation, "input_rows": input_rows, "result_rows": result_rows, "observed": observed, "maximum": maximum}
    return CohortBetaFrontierBenchmarkCase(f"benchmark:{operation}", operation, input_rows, result_rows, maximum, observed, observed <= maximum and input_rows == 4 and result_rows == 4, content_hash(body, prefix="benchmark-case"))


def build_cohort_beta_frontier_benchmark_report(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierBenchmarkReport:
    cases = tuple(_case(operation, fixture, evaluation) for operation in ("C05", "C06", "C07", "C08"))
    total = sum(item.observed_work_units for item in cases)
    maximum = sum(item.max_work_units for item in cases)
    return CohortBetaFrontierBenchmarkReport(cases, total, maximum, all(item.accepted for item in cases), content_hash({"cases": cases, "total": total, "maximum": maximum}, prefix="benchmark"))


def benchmark_summary(report: CohortBetaFrontierBenchmarkReport) -> dict[str, Any]:
    return {"total_work_units": report.total_work_units, "max_work_units": report.max_work_units, "utilization_percent": round(100 * report.total_work_units / max(1, report.max_work_units), 2), "accepted": report.accepted, "operations": {item.operation: item.observed_work_units for item in report.cases}}


__all__ = ["CohortBetaFrontierBenchmarkCase", "CohortBetaFrontierBenchmarkReport", "benchmark_summary", "build_cohort_beta_frontier_benchmark_report"]
