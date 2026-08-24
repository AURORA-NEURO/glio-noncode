"""Deterministic D16 case query helpers."""

from __future__ import annotations

from typing import Any

from .platform_execution_architecture_contracts import (
    PlatformExecutionEvaluation,
    PlatformExecutionFixture,
)
from .platform_execution_architecture_operations import evaluate_platform_execution_fixture
from .platform_execution_architecture_public_data import default_platform_execution_fixture


def query_platform_execution(
    *,
    fixture: PlatformExecutionFixture | None = None,
    evaluation: PlatformExecutionEvaluation | None = None,
    operation: str | None = None,
    family: str | None = None,
    scenario: str | None = None,
) -> tuple[dict[str, Any], ...]:
    selected = fixture or default_platform_execution_fixture()
    resolved = evaluation or evaluate_platform_execution_fixture(selected)
    cases = {item.case_id: item for item in selected.cases}
    rows = []
    for execution in resolved.executions:
        case = cases[execution.case_id]
        if operation and case.operation_id != operation and case.operation.value != operation:
            continue
        if family and case.family.value != family:
            continue
        if scenario and case.scenario.value != scenario:
            continue
        rows.append(
            {
                "case_id": case.case_id,
                "operation_id": case.operation_id,
                "operation": case.operation,
                "family": case.family,
                "plane": case.plane,
                "scenario": case.scenario,
                "state": execution.observed_state,
                "issue_codes": execution.observed_issue_codes,
                "output_address": execution.output_address,
            }
        )
    return tuple(rows)


__all__ = ["query_platform_execution"]
