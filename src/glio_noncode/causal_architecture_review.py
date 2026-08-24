"""Review routing for D11 causal controls."""

from __future__ import annotations

from .causal_architecture_contracts import (
    CausalArchitectureEvaluation,
    CausalArchitectureReviewItem,
    CausalArchitectureReviewQueue,
    CausalArchitectureScenario,
    addressed,
)


def build_causal_architecture_review_queue(
    evaluation: CausalArchitectureEvaluation,
) -> CausalArchitectureReviewQueue:
    items = []
    for receipt, execution in zip(evaluation.receipts, evaluation.executions, strict=True):
        if receipt.expected_state.value == "accepted":
            continue
        body = {
            "case_id": receipt.case_id,
            "operation_id": receipt.operation_id,
            "scenario": execution.scenario,
            "priority": "high"
            if execution.scenario is CausalArchitectureScenario.CONTROL_C
            else "normal",
            "blocking": True,
            "reason": ", ".join(receipt.observed_issue_codes)
            or "bounded causal output requires review",
            "required_action": (
                "review context, evidence dependence, and limitations before release"
            ),
        }
        items.append(
            CausalArchitectureReviewItem(**body, content_address=addressed(body, "causal-review"))
        )
    return CausalArchitectureReviewQueue(
        evaluation.fixture_id,
        tuple(items),
        len(items) == 48,
        addressed(items, "causal-review-queue"),
    )


def causal_architecture_review_summary(queue: CausalArchitectureReviewQueue) -> dict[str, object]:
    return {
        "fixture_id": queue.fixture_id,
        "item_count": len(queue.items),
        "accepted": queue.accepted,
    }


__all__ = ["build_causal_architecture_review_queue", "causal_architecture_review_summary"]
