"""Operation-by-plane contract matrix for D08 review and release checks."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .cell_state_architecture_contracts import (
    CellStateArchitectureFixture,
    CellStateArchitectureOperation,
)


def build_cell_state_architecture_contract_matrix(
    fixture: CellStateArchitectureFixture,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for operation in fixture.operations:
        cases = tuple(item for item in fixture.cases if item.operation_id == operation.operation_id)
        positive = next(item for item in cases if item.scenario.value == "positive")
        rows.append(
            {
                "ordinal": operation.ordinal,
                "operation_id": operation.operation_id,
                "capability_id": operation.capability_id,
                "operation": operation.operation.value,
                "family": operation.family.value,
                "plane": operation.plane.value,
                "input_contract": operation.input_contract,
                "output_contract": operation.output_contract,
                "dependency_count": len(operation.dependencies),
                "source_count": len(operation.source_ids),
                "case_ids": [item.case_id for item in cases],
                "positive_result_state": positive.expected_result_state,
                "control_result_states": sorted(
                    {item.expected_result_state for item in cases if item is not positive}
                ),
            }
        )
    return tuple(rows)


def contract_matrix_summary(matrix: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    return {
        "operation_count": len(matrix),
        "family_counts": dict(sorted(Counter(item["family"] for item in matrix).items())),
        "plane_counts": dict(sorted(Counter(item["plane"] for item in matrix).items())),
        "positive_result_states": dict(
            sorted(Counter(item["positive_result_state"] for item in matrix).items())
        ),
        "fully_balanced": all(len(item["case_ids"]) == 4 for item in matrix),
    }


def contract_matrix_is_closed(fixture: CellStateArchitectureFixture) -> bool:
    matrix = build_cell_state_architecture_contract_matrix(fixture)
    return (
        len(matrix) == 16
        and {item["operation"] for item in matrix}
        == {item.value for item in CellStateArchitectureOperation}
        and contract_matrix_summary(matrix)["fully_balanced"]
    )


__all__ = [
    "build_cell_state_architecture_contract_matrix",
    "contract_matrix_is_closed",
    "contract_matrix_summary",
]
