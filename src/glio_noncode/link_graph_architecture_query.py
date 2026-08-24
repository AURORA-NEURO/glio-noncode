"""Review-safe D10 case and artifact queries."""

from __future__ import annotations

from .link_graph_architecture_contracts import LinkGraphArchitectureRuntime


def query_link_graph_architecture_cases(
    runtime: LinkGraphArchitectureRuntime,
    *,
    operation_id: str | None = None,
    family: str | None = None,
    scenario: str | None = None,
) -> tuple[dict[str, object], ...]:
    rows = []
    for case, execution, receipt in zip(
        runtime.fixture.cases,
        runtime.evaluation.executions,
        runtime.evaluation.receipts,
        strict=True,
    ):
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
                "delegate_record_id": case.delegate_record_id,
                "observed_result_state": execution.observed_result_state,
                "issue_codes": list(execution.observed_issue_codes),
                "passed": receipt.passed,
                "output_address": execution.output_address,
            }
        )
    return tuple(rows)


def query_link_graph_architecture_artifact(
    runtime: LinkGraphArchitectureRuntime, artifact_id: str
) -> dict[str, object] | None:
    return next(
        (item.to_dict() for item in runtime.artifacts if item.artifact_id == artifact_id), None
    )


__all__ = ["query_link_graph_architecture_artifact", "query_link_graph_architecture_cases"]
