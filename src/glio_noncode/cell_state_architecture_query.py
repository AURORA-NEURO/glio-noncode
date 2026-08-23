"""Small query surface over the D08 runtime graph."""

from __future__ import annotations

from .cell_state_architecture_contracts import CellStateArchitectureRuntime


def find_cell_state_cases(
    runtime: CellStateArchitectureRuntime,
    *,
    operation_id: str | None = None,
    family: str | None = None,
    scenario: str | None = None,
) -> tuple[dict[str, object], ...]:
    rows = []
    for case, execution in zip(runtime.fixture.cases, runtime.evaluation.executions, strict=True):
        if operation_id and case.operation_id != operation_id:
            continue
        if family and case.family.value != family:
            continue
        if scenario and case.scenario.value != scenario:
            continue
        rows.append(
            {
                "case_id": case.case_id,
                "operation_id": case.operation_id,
                "family": case.family.value,
                "scenario": case.scenario.value,
                "observed_state": execution.observed_state.value,
                "result_state": execution.observed_result_state,
                "output_address": execution.output_address,
            }
        )
    return tuple(rows)


def find_cell_state_artifact(
    runtime: CellStateArchitectureRuntime, artifact_id: str
) -> dict[str, object] | None:
    for artifact in runtime.artifacts:
        if artifact.artifact_id == artifact_id:
            return artifact.to_dict()
    return None


def query_cell_state_operations(runtime: CellStateArchitectureRuntime) -> tuple[str, ...]:
    return tuple(item.operation_id for item in runtime.fixture.operations)


__all__ = ["find_cell_state_artifact", "find_cell_state_cases", "query_cell_state_operations"]
