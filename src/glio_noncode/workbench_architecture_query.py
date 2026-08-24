"""Deterministic query helpers over the D15 fixture and evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .workbench_architecture_contracts import (
    WorkbenchArchitectureEvaluation,
    WorkbenchArchitectureFixture,
)
from .workbench_architecture_operations import evaluate_workbench_architecture_fixture
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def query_workbench_architecture(
    *,
    fixture: WorkbenchArchitectureFixture | None = None,
    evaluation: WorkbenchArchitectureEvaluation | None = None,
    operation: str | None = None,
    family: str | None = None,
    scenario: str | None = None,
) -> tuple[dict[str, Any], ...]:
    selected = fixture or default_workbench_architecture_fixture()
    resolved = evaluation or evaluate_workbench_architecture_fixture(selected)
    cases = {item.case_id: item for item in selected.cases}
    rows = []
    for execution in resolved.executions:
        case = cases[execution.case_id]
        if operation and case.operation.value != operation and case.operation_id != operation:
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


def workbench_architecture_query_values(
    rows: Iterable[dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    materialized = tuple(rows)
    return {
        "operations": tuple(sorted({item["operation"].value for item in materialized})),
        "families": tuple(sorted({item["family"].value for item in materialized})),
        "scenarios": tuple(sorted({item["scenario"].value for item in materialized})),
        "states": tuple(sorted({item["state"].value for item in materialized})),
    }


__all__ = ["query_workbench_architecture", "workbench_architecture_query_values"]
