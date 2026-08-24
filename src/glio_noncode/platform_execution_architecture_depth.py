"""Depth report for D16 execution and control coverage."""

from __future__ import annotations

from .platform_execution_architecture_contracts import (
    PlatformExecutionDepthReport,
    PlatformExecutionEvaluation,
    PlatformExecutionFixture,
    addressed,
)
from .platform_execution_architecture_public_data import default_platform_execution_fixture


def assess_platform_execution_depth(
    fixture: PlatformExecutionFixture | None = None,
    evaluation: PlatformExecutionEvaluation | None = None,
) -> PlatformExecutionDepthReport:
    selected = fixture or default_platform_execution_fixture()
    if evaluation is None:
        from .platform_execution_architecture_operations import evaluate_platform_execution_fixture

        evaluation = evaluate_platform_execution_fixture(selected)
    addresses = (
        {item.content_address for item in selected.sources}
        | {item.content_address for item in selected.operations}
        | {item.content_address for item in selected.cases}
        | {item.content_address for item in evaluation.checks}
        | {item.output_address for item in evaluation.executions}
    )
    states = {item.observed_state.value for item in evaluation.executions}
    issues = {issue for item in evaluation.executions for issue in item.observed_issue_codes}
    body = {
        "fixture_id": selected.fixture_id,
        "source_count": len(selected.sources),
        "operation_count": len(selected.operations),
        "case_count": len(selected.cases),
        "check_count": len(evaluation.checks),
        "addressed_count": len(addresses),
    }
    return PlatformExecutionDepthReport(
        selected.fixture_id,
        len(selected.sources),
        len(selected.operations),
        len(selected.cases),
        len(selected.positive_cases),
        len(selected.control_cases),
        len(selected.family_set),
        len(evaluation.checks),
        len(addresses),
        len(states),
        len(issues),
        addressed(body, "platform-execution-depth"),
    )


__all__ = ["assess_platform_execution_depth"]
