"""Sanitized case and operation views for dashboards and review screens."""

from __future__ import annotations

from typing import Any

from .cell_state_architecture_contracts import CellStateArchitectureRuntime
from .cell_state_architecture_normalization import review_safe_projection


def build_cell_state_case_views(
    runtime: CellStateArchitectureRuntime,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        review_safe_projection(
            {
                "case_id": case.case_id,
                "operation_id": case.operation_id,
                "capability_id": case.capability_id,
                "family": case.family.value,
                "plane": case.plane.value,
                "scenario": case.scenario.value,
                "context_key": case.context_key,
                "expected_state": case.expected_state.value,
                "expected_result_state": case.expected_result_state,
                "observed_state": execution.observed_state.value,
                "observed_result_state": execution.observed_result_state,
                "issue_codes": list(execution.issue_codes),
                "counts": execution.counts,
                "output_address": execution.output_address,
                "passed": next(
                    receipt.passed
                    for receipt in runtime.evaluation.receipts
                    if receipt.case_id == case.case_id
                ),
            }
        )
        for case, execution in zip(
            runtime.fixture.cases, runtime.evaluation.executions, strict=True
        )
    )


def build_cell_state_operation_views(
    runtime: CellStateArchitectureRuntime,
) -> tuple[dict[str, Any], ...]:
    views: list[dict[str, Any]] = []
    case_views = build_cell_state_case_views(runtime)
    for operation in runtime.fixture.operations:
        cases = tuple(item for item in case_views if item["operation_id"] == operation.operation_id)
        views.append(
            {
                "operation_id": operation.operation_id,
                "capability_id": operation.capability_id,
                "ordinal": operation.ordinal,
                "operation": operation.operation.value,
                "family": operation.family.value,
                "plane": operation.plane.value,
                "positive_count": sum(item["scenario"] == "positive" for item in cases),
                "control_count": sum(item["scenario"] != "positive" for item in cases),
                "passed_count": sum(item["passed"] for item in cases),
                "case_ids": [item["case_id"] for item in cases],
            }
        )
    return tuple(views)


def build_cell_state_release_view(runtime: CellStateArchitectureRuntime) -> dict[str, Any]:
    return {
        "release_id": runtime.release.release_id,
        "state": runtime.release.state.value,
        "accepted": runtime.accepted,
        "artifact_count": len(runtime.artifacts),
        "stage_count": len(runtime.stages),
        "review_item_count": len(runtime.review_queue.items),
        "limitations": list(runtime.release.limitations),
    }


__all__ = [
    "build_cell_state_case_views",
    "build_cell_state_operation_views",
    "build_cell_state_release_view",
]
