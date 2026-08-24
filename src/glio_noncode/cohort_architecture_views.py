"""Sanitized D12 case and operation views."""

from __future__ import annotations

from typing import Any

from .cohort_architecture_contracts import CohortArchitectureRuntime


def cohort_architecture_case_views(
    runtime: CohortArchitectureRuntime,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "operation": case.operation.value,
            "family": case.family.value,
            "plane": case.plane.value,
            "scenario": case.scenario.value,
            "delegate_record_id": case.delegate_record_id,
            "delegate_class": case.delegate_class,
            "delegate_context_key": case.delegate_context_key,
            "expected_state": case.expected_state.value,
            "observed_state": execution.observed_state.value,
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


def cohort_architecture_operation_views(
    runtime: CohortArchitectureRuntime,
) -> tuple[dict[str, Any], ...]:
    cases = cohort_architecture_case_views(runtime)
    return tuple(
        {
            "operation_id": operation.operation_id,
            "operation": operation.operation.value,
            "delegate_operation": operation.delegate_operation,
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


__all__ = ["cohort_architecture_case_views", "cohort_architecture_operation_views"]
