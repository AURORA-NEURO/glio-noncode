"""Depth accounting for D15 workbench coverage and controls."""

from __future__ import annotations

from .workbench_architecture_contracts import (
    WorkbenchArchitectureDepthReport,
    WorkbenchArchitectureEvaluation,
    WorkbenchArchitectureFixture,
    addressed,
)
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def assess_workbench_architecture_depth(
    fixture: WorkbenchArchitectureFixture | None = None,
    evaluation: WorkbenchArchitectureEvaluation | None = None,
) -> WorkbenchArchitectureDepthReport:
    selected = fixture or default_workbench_architecture_fixture()
    if evaluation is None:
        from .workbench_architecture_operations import evaluate_workbench_architecture_fixture

        evaluation = evaluate_workbench_architecture_fixture(selected)
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
    return WorkbenchArchitectureDepthReport(
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
        addressed(body, "workbench-architecture-depth"),
    )


def workbench_architecture_depth_summary(
    report: WorkbenchArchitectureDepthReport,
) -> dict[str, object]:
    return {
        "fixture_id": report.fixture_id,
        "source_count": report.source_count,
        "operation_count": report.operation_count,
        "case_count": report.case_count,
        "positive_count": report.positive_count,
        "control_count": report.control_count,
        "check_count": report.check_count,
        "addressed_count": report.addressed_count,
        "state_count": report.state_count,
        "issue_code_count": report.issue_code_count,
    }


__all__ = ["assess_workbench_architecture_depth", "workbench_architecture_depth_summary"]
