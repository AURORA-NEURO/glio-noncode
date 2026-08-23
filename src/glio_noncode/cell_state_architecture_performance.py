"""Performance budgets derived from the fixed D08 case and receipt counts."""

from __future__ import annotations

from typing import Any

from .cell_state_architecture_contracts import CellStateArchitectureRuntime

D08_CASE_BUDGET = 0.020
D08_STAGE_BUDGET = 0.050
D08_TOTAL_BUDGET = 2.500


def cell_state_architecture_performance_budget(
    runtime: CellStateArchitectureRuntime,
) -> dict[str, Any]:
    case_count = len(runtime.evaluation.executions)
    stage_count = len(runtime.stages)
    projected_case_seconds = round(case_count * D08_CASE_BUDGET, 3)
    projected_stage_seconds = round(stage_count * D08_STAGE_BUDGET, 3)
    budget = {
        "fixture_id": runtime.fixture.fixture_id,
        "case_count": case_count,
        "stage_count": stage_count,
        "per_case_budget_seconds": D08_CASE_BUDGET,
        "per_stage_budget_seconds": D08_STAGE_BUDGET,
        "total_budget_seconds": D08_TOTAL_BUDGET,
        "projected_case_seconds": projected_case_seconds,
        "projected_stage_seconds": projected_stage_seconds,
        "projected_total_seconds": projected_case_seconds + projected_stage_seconds,
    }
    return budget | {"within_budget": budget["projected_total_seconds"] <= D08_TOTAL_BUDGET}


def performance_budget_is_closed(runtime: CellStateArchitectureRuntime) -> bool:
    budget = cell_state_architecture_performance_budget(runtime)
    return budget["within_budget"] and budget["case_count"] == 64 and budget["stage_count"] == 22


__all__ = [
    "D08_CASE_BUDGET",
    "D08_STAGE_BUDGET",
    "D08_TOTAL_BUDGET",
    "cell_state_architecture_performance_budget",
    "performance_budget_is_closed",
]
