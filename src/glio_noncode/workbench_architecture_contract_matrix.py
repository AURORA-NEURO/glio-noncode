"""Operation, delegate, state, and control contract matrix for D15."""

from __future__ import annotations

from typing import Any

from .workbench_architecture_contracts import (
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureScenario,
    addressed,
)
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def workbench_architecture_contract_matrix(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> tuple[dict[str, Any], ...]:
    selected = fixture or default_workbench_architecture_fixture()
    rows = []
    for operation in selected.operations:
        scenario_map = {
            item.scenario.value: item
            for item in selected.cases
            if item.operation_id == operation.operation_id
        }
        body = {
            "operation_id": operation.operation_id,
            "capability_id": operation.capability_id,
            "ordinal": operation.ordinal,
            "operation": operation.operation,
            "family": operation.family,
            "plane": operation.plane,
            "delegate_operation": operation.delegate_operation,
            "input_contract": operation.input_contract,
            "output_contract": operation.output_contract,
            "dependencies": operation.dependencies,
            "source_count": len(operation.source_ids),
            "scenario_states": {
                scenario.value: scenario_map[scenario.value].expected_state
                for scenario in WorkbenchArchitectureScenario
            },
            "scenario_issue_codes": {
                scenario.value: scenario_map[scenario.value].expected_issue_codes
                for scenario in WorkbenchArchitectureScenario
            },
            "control_policy": operation.control_policy,
        }
        rows.append(
            body | {"content_address": addressed(body, "workbench-architecture-contract-row")}
        )
    return tuple(rows)


def workbench_architecture_contract_matrix_summary(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> dict[str, object]:
    rows = workbench_architecture_contract_matrix(fixture)
    return {
        "row_count": len(rows),
        "operation_ids": [item["operation_id"] for item in rows],
        "families": sorted({item["family"].value for item in rows}),
        "planes": sorted({item["plane"].value for item in rows}),
        "dependency_edge_count": sum(len(item["dependencies"]) for item in rows),
        "address_count": len({item["content_address"] for item in rows}),
    }


__all__ = [
    "workbench_architecture_contract_matrix",
    "workbench_architecture_contract_matrix_summary",
]
