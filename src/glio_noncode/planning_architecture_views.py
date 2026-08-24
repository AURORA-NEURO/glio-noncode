"""Stable projections for reports, tables, and downstream review."""

from __future__ import annotations

from typing import Any

from .planning_architecture_contracts import (
    PlanningArchitectureCase,
    PlanningArchitectureEvaluation,
    PlanningArchitectureFixture,
    PlanningArchitectureRuntime,
    jsonable,
)


def planning_architecture_case_view(
    case: PlanningArchitectureCase,
    *,
    include_payload: bool = False,
) -> dict[str, Any]:
    value = case.to_dict(include_payload=include_payload)
    value["projection"] = "case_with_payload" if include_payload else "case_sanitized"
    return value


def planning_architecture_evaluation_view(
    evaluation: PlanningArchitectureEvaluation,
) -> dict[str, Any]:
    return {
        "fixture_id": evaluation.fixture_id,
        "context_key": evaluation.context_key,
        "state": evaluation.state,
        "accepted": evaluation.accepted,
        "execution_count": len(evaluation.executions),
        "receipt_count": len(evaluation.receipts),
        "check_count": len(evaluation.checks),
        "failed_check_ids": [item.check_id for item in evaluation.checks if not item.passed],
        "content_address": evaluation.content_address,
    }


def planning_architecture_runtime_view(
    runtime: PlanningArchitectureRuntime,
) -> dict[str, Any]:
    return {
        "fixture_id": runtime.fixture.fixture_id,
        "accepted": runtime.accepted,
        "stage_count": len(runtime.stages),
        "stage_ids": [item.stage_id for item in runtime.stages],
        "source_count": len(runtime.fixture.sources),
        "operation_count": len(runtime.fixture.operations),
        "case_count": len(runtime.fixture.cases),
        "evaluation": planning_architecture_evaluation_view(runtime.evaluation),
        "review_item_count": len(runtime.review_queue.items),
        "artifact_ids": [item.artifact_id for item in runtime.artifacts],
        "release_state": runtime.release.state.value,
        "depth": jsonable(runtime.depth),
        "quality": jsonable(runtime.quality),
        "content_address": runtime.content_address,
    }


def planning_architecture_case_table(
    fixture: PlanningArchitectureFixture,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "family": case.family.value,
            "scenario": case.scenario.value,
            "delegate_record_id": case.delegate_record_id,
            "expected_state": case.expected_state.value,
            "issue_codes": list(case.expected_issue_codes),
            "source_count": len(case.source_ids),
            "content_address": case.content_address,
        }
        for case in fixture.cases
    )


__all__ = [
    "planning_architecture_case_table",
    "planning_architecture_case_view",
    "planning_architecture_evaluation_view",
    "planning_architecture_runtime_view",
]
