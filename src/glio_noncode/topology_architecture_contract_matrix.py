"""Operation and scenario matrix for D09 release review."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .topology_architecture_contracts import (
    TopologyArchitectureFixture,
    TopologyArchitectureOperation,
)


def build_topology_architecture_contract_matrix(
    fixture: TopologyArchitectureFixture,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for operation in fixture.operations:
        cases = tuple(item for item in fixture.cases if item.operation_id == operation.operation_id)
        positive = next(item for item in cases if item.scenario.value == "positive")
        rows.append(
            {
                "operation_id": operation.operation_id,
                "capability_id": operation.capability_id,
                "ordinal": operation.ordinal,
                "operation": operation.operation.value,
                "family": operation.family.value,
                "plane": operation.plane.value,
                "dependency_count": len(operation.dependencies),
                "source_count": len(operation.source_ids),
                "case_count": len(cases),
                "positive_result_state": positive.expected_result_state,
                "control_result_states": sorted(
                    {item.expected_result_state for item in cases if item is not positive}
                ),
            }
        )
    return tuple(rows)


def topology_architecture_contract_matrix_summary(
    matrix: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        "operation_count": len(matrix),
        "family_counts": dict(sorted(Counter(item["family"] for item in matrix).items())),
        "plane_counts": dict(sorted(Counter(item["plane"] for item in matrix).items())),
        "result_states": dict(
            sorted(Counter(item["positive_result_state"] for item in matrix).items())
        ),
        "balanced": all(item["case_count"] == 4 for item in matrix),
    }


def topology_architecture_contract_matrix_is_closed(fixture: TopologyArchitectureFixture) -> bool:
    matrix = build_topology_architecture_contract_matrix(fixture)
    return (
        len(matrix) == 16
        and {item["operation"] for item in matrix}
        == {item.value for item in TopologyArchitectureOperation}
        and topology_architecture_contract_matrix_summary(matrix)["balanced"]
    )


__all__ = [
    "build_topology_architecture_contract_matrix",
    "topology_architecture_contract_matrix_is_closed",
    "topology_architecture_contract_matrix_summary",
]
