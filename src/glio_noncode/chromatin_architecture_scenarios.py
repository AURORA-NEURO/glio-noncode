"""Scenario matrix covering the four D07 positive/control paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import (
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    ChromatinArchitectureScenario,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureScenarioRow:
    case_id: str
    operation_id: str
    family: str
    scenario: ChromatinArchitectureScenario
    expected_state: str
    observed_state: str
    expected_result_state: str
    observed_result_state: str
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureScenarioMatrix:
    fixture_id: str
    rows: tuple[ChromatinArchitectureScenarioRow, ...]
    scenario_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_architecture_scenario_matrix(
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
) -> ChromatinArchitectureScenarioMatrix:
    cases = {item.case_id: item for item in fixture.cases}
    rows = tuple(
        ChromatinArchitectureScenarioRow(
            case_id=receipt.case_id,
            operation_id=receipt.operation_id,
            family=receipt.family.value,
            scenario=cases[receipt.case_id].scenario,
            expected_state=receipt.expected_state.value,
            observed_state=receipt.observed_state.value,
            expected_result_state=receipt.expected_result_state,
            observed_result_state=receipt.observed_result_state,
            passed=receipt.passed,
            content_address=addressed(receipt, "chromatin-scenario-row"),
        )
        for receipt in evaluation.receipts
    )
    counts = {
        scenario.value: sum(item.scenario is scenario for item in rows)
        for scenario in ChromatinArchitectureScenario
    }
    body = {"fixture_id": fixture.fixture_id, "rows": rows, "scenario_counts": counts}
    return ChromatinArchitectureScenarioMatrix(
        fixture.fixture_id,
        rows,
        counts,
        len(rows) == 64 and all(item.passed for item in rows),
        addressed(body, "chromatin-scenarios"),
    )


def chromatin_architecture_scenario_summary(
    matrix: ChromatinArchitectureScenarioMatrix,
) -> dict[str, Any]:
    return {
        "fixture_id": matrix.fixture_id,
        "row_count": len(matrix.rows),
        "scenario_counts": dict(matrix.scenario_counts),
        "accepted": matrix.accepted,
        "content_address": matrix.content_address,
    }


__all__ = [
    "ChromatinArchitectureScenarioMatrix",
    "ChromatinArchitectureScenarioRow",
    "build_chromatin_architecture_scenario_matrix",
    "chromatin_architecture_scenario_summary",
]
