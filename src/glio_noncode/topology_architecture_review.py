"""Review routing for D09 held context, input, and identity controls."""

from __future__ import annotations

from .topology_architecture_contracts import (
    TopologyArchitectureEvaluation,
    TopologyArchitectureReviewItem,
    TopologyArchitectureReviewQueue,
    TopologyArchitectureScenario,
    addressed,
)


def build_topology_architecture_review_queue(
    evaluation: TopologyArchitectureEvaluation,
) -> TopologyArchitectureReviewQueue:
    items: list[TopologyArchitectureReviewItem] = []
    for execution, receipt in zip(evaluation.executions, evaluation.receipts, strict=True):
        if receipt.expected_state.value != "review":
            continue
        priority = (
            "critical"
            if execution.scenario is TopologyArchitectureScenario.IDENTITY_CONFLICT
            else "high"
        )
        reason = ",".join(receipt.observed_issue_codes) or "topology control held for review"
        body = {
            "case_id": receipt.case_id,
            "operation_id": receipt.operation_id,
            "scenario": execution.scenario,
            "priority": priority,
            "blocking": True,
            "reason": reason,
            "required_action": (
                "reconcile exact topology context and declared identity before retry"
            ),
        }
        items.append(
            TopologyArchitectureReviewItem(
                **body, content_address=addressed(body, "topology-review")
            )
        )
    body = {"fixture_id": evaluation.fixture_id, "items": items, "accepted": evaluation.accepted}
    return TopologyArchitectureReviewQueue(
        evaluation.fixture_id,
        tuple(items),
        evaluation.accepted,
        addressed(body, "topology-review-queue"),
    )


def topology_architecture_review_summary(
    queue: TopologyArchitectureReviewQueue,
) -> dict[str, object]:
    return {
        "fixture_id": queue.fixture_id,
        "item_count": len(queue.items),
        "blocking_count": sum(item.blocking for item in queue.items),
        "critical_count": sum(item.priority == "critical" for item in queue.items),
        "accepted": queue.accepted,
    }


__all__ = ["build_topology_architecture_review_queue", "topology_architecture_review_summary"]
