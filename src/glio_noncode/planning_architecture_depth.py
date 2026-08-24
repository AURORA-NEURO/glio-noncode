"""D13 depth and evidence-density accounting."""

from __future__ import annotations

from .planning_architecture_contracts import (
    PlanningArchitectureDepthReport,
    PlanningArchitectureEvaluation,
    PlanningArchitectureFixture,
    addressed,
)
from .planning_architecture_public_data import default_planning_architecture_fixture


def assess_planning_architecture_depth(
    fixture: PlanningArchitectureFixture | None = None,
    evaluation: PlanningArchitectureEvaluation | None = None,
) -> PlanningArchitectureDepthReport:
    selected = fixture or default_planning_architecture_fixture()
    if evaluation is None:
        from .planning_architecture_operations import evaluate_planning_architecture_fixture

        evaluation = evaluate_planning_architecture_fixture(selected)
    states = {item.observed_state.value for item in evaluation.executions}
    issues = {issue for item in evaluation.executions for issue in item.observed_issue_codes}
    addresses = {
        selected.content_address,
        *(item.content_address for item in selected.sources),
        *(item.content_address for item in selected.operations),
        *(item.content_address for item in selected.cases),
        *(item.content_address for item in evaluation.checks),
        *(item.output_address for item in evaluation.executions),
    }
    body = {
        "fixture_id": selected.fixture_id,
        "source_count": len(selected.sources),
        "operation_count": len(selected.operations),
        "case_count": len(selected.cases),
        "positive_count": len(selected.positive_cases),
        "control_count": len(selected.control_cases),
        "family_count": len(selected.family_set),
        "check_count": len(evaluation.checks),
        "addressed_count": len(addresses),
        "state_count": len(states),
        "issue_code_count": len(issues),
    }
    return PlanningArchitectureDepthReport(
        **body,
        content_address=addressed(body, "planning-depth"),
    )


def planning_architecture_depth_summary(
    depth: PlanningArchitectureDepthReport,
) -> dict[str, object]:
    return {
        "fixture_id": depth.fixture_id,
        "source_count": depth.source_count,
        "operation_count": depth.operation_count,
        "case_count": depth.case_count,
        "positive_count": depth.positive_count,
        "control_count": depth.control_count,
        "family_count": depth.family_count,
        "check_count": depth.check_count,
        "addressed_count": depth.addressed_count,
        "state_count": depth.state_count,
        "issue_code_count": depth.issue_code_count,
    }


__all__ = ["assess_planning_architecture_depth", "planning_architecture_depth_summary"]
