"""Sanitized D10 case and operation views."""

from __future__ import annotations

from typing import Any

from .link_graph_architecture_contracts import LinkGraphArchitectureRuntime


def link_graph_architecture_case_views(
    runtime: LinkGraphArchitectureRuntime,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "family": case.family.value,
            "plane": case.plane.value,
            "scenario": case.scenario.value,
            "delegate_record_id": case.delegate_record_id,
            "delegate_context_key": case.delegate_context_key,
            "expected_state": case.expected_state.value,
            "observed_state": execution.observed_state.value,
            "expected_result_state": case.expected_result_state,
            "observed_result_state": execution.observed_result_state,
            "issue_codes": list(execution.observed_issue_codes),
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


def link_graph_architecture_operation_views(
    runtime: LinkGraphArchitectureRuntime,
) -> tuple[dict[str, Any], ...]:
    cases = link_graph_architecture_case_views(runtime)
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


__all__ = ["link_graph_architecture_case_views", "link_graph_architecture_operation_views"]
