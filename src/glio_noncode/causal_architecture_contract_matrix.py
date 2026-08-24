"""D11 operation and scenario matrix."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .causal_architecture_contracts import CausalArchitectureFixture, CausalArchitectureOperation


def build_causal_architecture_contract_matrix(
    fixture: CausalArchitectureFixture,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "operation_id": operation.operation_id,
            "operation": operation.operation.value,
            "family": operation.family.value,
            "plane": operation.plane.value,
            "case_count": sum(
                item.operation_id == operation.operation_id for item in fixture.cases
            ),
            "source_count": len(operation.source_ids),
            "scenarios": tuple(
                item.scenario.value
                for item in fixture.cases
                if item.operation_id == operation.operation_id
            ),
        }
        for operation in fixture.operations
    )


def causal_architecture_contract_matrix_summary(
    matrix: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        "operation_count": len(matrix),
        "family_counts": dict(sorted(Counter(item["family"] for item in matrix).items())),
        "plane_counts": dict(sorted(Counter(item["plane"] for item in matrix).items())),
        "balanced": all(
            item["case_count"] == 4
            and item["scenarios"] == ("positive", "control_a", "control_b", "control_c")
            for item in matrix
        ),
    }


def causal_architecture_contract_matrix_is_closed(fixture: CausalArchitectureFixture) -> bool:
    matrix = build_causal_architecture_contract_matrix(fixture)
    return (
        len(matrix) == 16
        and {item["operation"] for item in matrix}
        == {item.value for item in CausalArchitectureOperation}
        and causal_architecture_contract_matrix_summary(matrix)["balanced"]
    )


__all__ = [
    "build_causal_architecture_contract_matrix",
    "causal_architecture_contract_matrix_is_closed",
    "causal_architecture_contract_matrix_summary",
]
