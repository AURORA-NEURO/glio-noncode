"""Query surface over D09 runtime receipts."""

from __future__ import annotations

from .topology_architecture_contracts import TopologyArchitectureRuntime


def query_topology_architecture_cases(
    runtime: TopologyArchitectureRuntime,
    *,
    operation_id: str | None = None,
    family: str | None = None,
    scenario: str | None = None,
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
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
                "plane": case.plane.value,
                "scenario": case.scenario.value,
                "observed_state": execution.observed_state.value,
                "result_state": execution.observed_result_state,
                "issue_codes": list(execution.issue_codes),
                "output_address": execution.output_address,
            }
        )
    return tuple(rows)


def query_topology_architecture_artifact(
    runtime: TopologyArchitectureRuntime, artifact_id: str
) -> dict[str, object] | None:
    return next(
        (item.to_dict() for item in runtime.artifacts if item.artifact_id == artifact_id), None
    )


__all__ = ["query_topology_architecture_artifact", "query_topology_architecture_cases"]
