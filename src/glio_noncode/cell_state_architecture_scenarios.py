"""Scenario matrix used to demonstrate D08 boundary behavior."""

from __future__ import annotations

from typing import Any

from .cell_state_architecture_contracts import (
    CellStateArchitectureFixture,
    CellStateArchitectureScenario,
)


def cell_state_architecture_scenario_matrix(
    fixture: CellStateArchitectureFixture,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for scenario in CellStateArchitectureScenario:
        cases = tuple(item for item in fixture.cases if item.scenario is scenario)
        rows.append(
            {
                "scenario": scenario.value,
                "case_count": len(cases),
                "operation_ids": [item.operation_id for item in cases],
                "contexts": sorted({item.context_key for item in cases}),
                "expected_states": sorted({item.expected_state.value for item in cases}),
                "expected_result_states": sorted({item.expected_result_state for item in cases}),
                "purpose": _purpose(scenario),
            }
        )
    return tuple(rows)


def _purpose(scenario: CellStateArchitectureScenario) -> str:
    return {
        CellStateArchitectureScenario.POSITIVE: "exercise a declared public aggregate path",
        CellStateArchitectureScenario.FOREIGN_CONTEXT: "prove exact-context refusal",
        CellStateArchitectureScenario.MALFORMED_INPUT: (
            "prove malformed input is held before delegation"
        ),
        CellStateArchitectureScenario.IDENTITY_CONFLICT: (
            "prove identity contradiction is review-held"
        ),
    }[scenario]


def scenario_case_ids(
    fixture: CellStateArchitectureFixture, scenario: CellStateArchitectureScenario
) -> tuple[str, ...]:
    return tuple(item.case_id for item in fixture.cases if item.scenario is scenario)


__all__ = ["cell_state_architecture_scenario_matrix", "scenario_case_ids"]
