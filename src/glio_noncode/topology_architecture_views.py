"""Review-safe D09 case and operation views."""

from __future__ import annotations

from typing import Any

from .topology_architecture_contracts import TopologyArchitectureRuntime


def topology_architecture_case_views(
    runtime: TopologyArchitectureRuntime,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "family": case.family.value,
            "plane": case.plane.value,
            "scenario": case.scenario.value,
            "context_key": case.context_key,
            "expected_state": case.expected_state.value,
            "expected_result_state": case.expected_result_state,
            "observed_state": execution.observed_state.value,
            "observed_result_state": execution.observed_result_state,
            "issue_codes": list(execution.issue_codes),
            "passed": receipt.passed,
            "output_address": execution.output_address,
        }
        for case, execution, receipt in zip(
            runtime.fixture.cases,
            runtime.evaluation.executions,
            runtime.evaluation.receipts,
            strict=True,
        )
    )


def topology_architecture_operation_views(
    runtime: TopologyArchitectureRuntime,
) -> tuple[dict[str, Any], ...]:
    cases = topology_architecture_case_views(runtime)
    return tuple(
        {
            "operation_id": operation.operation_id,
            "operation": operation.operation.value,
            "family": operation.family.value,
            "plane": operation.plane.value,
            "positive_count": sum(
                item["scenario"] == "positive"
                for item in cases
                if item["operation_id"] == operation.operation_id
            ),
            "control_count": sum(
                item["scenario"] != "positive"
                for item in cases
                if item["operation_id"] == operation.operation_id
            ),
            "passed_count": sum(
                item["passed"] for item in cases if item["operation_id"] == operation.operation_id
            ),
        }
        for operation in runtime.fixture.operations
    )


__all__ = ["topology_architecture_case_views", "topology_architecture_operation_views"]
