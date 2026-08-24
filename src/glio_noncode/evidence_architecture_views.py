"""Stable compact views for D14 reports and command output."""

from __future__ import annotations

from typing import Any

from .evidence_architecture_contracts import (
    EvidenceArchitectureEvaluation,
    EvidenceArchitectureRuntime,
)


def evidence_architecture_evaluation_view(
    evaluation: EvidenceArchitectureEvaluation,
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
        "state_counts": {
            state: sum(item.observed_state.value == state for item in evaluation.executions)
            for state in sorted({item.observed_state.value for item in evaluation.executions})
        },
    }


def evidence_architecture_runtime_view(
    runtime: EvidenceArchitectureRuntime,
) -> dict[str, Any]:
    return {
        "fixture_id": runtime.fixture.fixture_id,
        "accepted": runtime.accepted,
        "stage_count": len(runtime.stages),
        "stage_ids": [item.stage_id for item in runtime.stages],
        "release_state": runtime.release.state.value,
        "review_item_count": len(runtime.review_queue.items),
        "artifact_count": len(runtime.artifacts),
        "depth": runtime.depth.to_dict(),
        "quality": runtime.quality.to_dict(),
        "content_address": runtime.content_address,
    }


def evidence_architecture_case_view(
    evaluation: EvidenceArchitectureEvaluation,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "case_id": item.case_id,
            "operation": item.operation.value,
            "family": item.family.value,
            "scenario": item.scenario.value,
            "state": item.observed_state.value,
            "issue_codes": item.observed_issue_codes,
            "output_address": item.output_address,
        }
        for item in evaluation.executions
    )


__all__ = [
    "evidence_architecture_case_view",
    "evidence_architecture_evaluation_view",
    "evidence_architecture_runtime_view",
]
