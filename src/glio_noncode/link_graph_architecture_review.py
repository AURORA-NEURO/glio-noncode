"""Review routing for D10 held link outcomes."""

from __future__ import annotations

from .link_graph_architecture_contracts import (
    LinkGraphArchitectureEvaluation,
    LinkGraphArchitectureReviewItem,
    LinkGraphArchitectureReviewQueue,
    LinkGraphArchitectureScenario,
    addressed,
)


def build_link_graph_architecture_review_queue(
    evaluation: LinkGraphArchitectureEvaluation,
) -> LinkGraphArchitectureReviewQueue:
    items = []
    for receipt in evaluation.receipts:
        if receipt.expected_state.value == "accepted":
            continue
        scenario = next(
            item.scenario for item in evaluation.executions if item.case_id == receipt.case_id
        )
        body = {
            "case_id": receipt.case_id,
            "operation_id": receipt.operation_id,
            "scenario": scenario,
            "priority": "high" if scenario is LinkGraphArchitectureScenario.CONTROL_C else "normal",
            "blocking": True,
            "reason": ", ".join(receipt.observed_issue_codes) or "delegate result requires review",
            "required_action": "review link evidence, context, and method support before release",
        }
        items.append(
            LinkGraphArchitectureReviewItem(**body, content_address=addressed(body, "link-review"))
        )
    return LinkGraphArchitectureReviewQueue(
        evaluation.fixture_id, tuple(items), len(items) == 48, addressed(items, "link-review-queue")
    )


def link_graph_architecture_review_summary(
    queue: LinkGraphArchitectureReviewQueue,
) -> dict[str, object]:
    return {
        "fixture_id": queue.fixture_id,
        "item_count": len(queue.items),
        "accepted": queue.accepted,
    }


__all__ = ["build_link_graph_architecture_review_queue", "link_graph_architecture_review_summary"]
