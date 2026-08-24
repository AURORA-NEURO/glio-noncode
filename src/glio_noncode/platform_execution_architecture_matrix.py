"""D16 operation, state, and control matrix."""

from __future__ import annotations

from typing import Any

from .platform_execution_architecture_contracts import (
    PlatformExecutionFixture,
    PlatformExecutionScenario,
    addressed,
)
from .platform_execution_architecture_public_data import default_platform_execution_fixture


def platform_execution_contract_matrix(
    fixture: PlatformExecutionFixture | None = None,
) -> tuple[dict[str, Any], ...]:
    selected = fixture or default_platform_execution_fixture()
    rows = []
    for operation in selected.operations:
        cases = {
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
            "scenario_states": {
                scenario.value: cases[scenario.value].expected_state
                for scenario in PlatformExecutionScenario
            },
            "scenario_issue_codes": {
                scenario.value: cases[scenario.value].expected_issue_codes
                for scenario in PlatformExecutionScenario
            },
            "control_policy": operation.control_policy,
        }
        rows.append(body | {"content_address": addressed(body, "platform-execution-contract-row")})
    return tuple(rows)


__all__ = ["platform_execution_contract_matrix"]
