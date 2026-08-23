"""Review queue construction for held D08 cases."""

from __future__ import annotations

from .cell_state_architecture_contracts import (
    CellStateArchitectureEvaluation,
    CellStateArchitectureReviewItem,
    CellStateArchitectureReviewQueue,
    CellStateArchitectureScenario,
    addressed,
)


def build_cell_state_architecture_review_queue(
    evaluation: CellStateArchitectureEvaluation,
) -> CellStateArchitectureReviewQueue:
    items: list[CellStateArchitectureReviewItem] = []
    for receipt in evaluation.receipts:
        if receipt.expected_state.value != "review":
            continue
        scenario = next(
            case.scenario for case in _fixture_cases(evaluation) if case.case_id == receipt.case_id
        )
        priority = (
            "critical" if scenario is CellStateArchitectureScenario.IDENTITY_CONFLICT else "high"
        )
        reason = ",".join(receipt.observed_issue_codes) or "review-held control path"
        body = {
            "case_id": receipt.case_id,
            "operation_id": receipt.operation_id,
            "scenario": scenario,
            "priority": priority,
            "blocking": True,
            "reason": reason,
            "required_action": (
                "retain hold until exact context and declared identity are reconciled"
            ),
        }
        items.append(
            CellStateArchitectureReviewItem(
                **body, content_address=addressed(body, "cell-state-review")
            )
        )
    body = {"fixture_id": evaluation.fixture_id, "items": items, "accepted": evaluation.accepted}
    return CellStateArchitectureReviewQueue(
        evaluation.fixture_id,
        tuple(items),
        evaluation.accepted,
        addressed(body, "cell-state-review-queue"),
    )


def _fixture_cases(evaluation: CellStateArchitectureEvaluation):
    """Evaluation receipts do not duplicate scenarios; derive them from execution rows."""
    return tuple(
        type("CaseView", (), {"case_id": item.case_id, "scenario": item.scenario})
        for item in evaluation.executions
    )


def review_summary(queue: CellStateArchitectureReviewQueue) -> dict[str, object]:
    return {
        "fixture_id": queue.fixture_id,
        "item_count": len(queue.items),
        "blocking_count": sum(item.blocking for item in queue.items),
        "priority_counts": {
            priority: sum(item.priority == priority for item in queue.items)
            for priority in ("critical", "high", "normal")
        },
        "accepted": queue.accepted,
        "content_address": queue.content_address,
    }


__all__ = ["build_cell_state_architecture_review_queue", "review_summary"]
