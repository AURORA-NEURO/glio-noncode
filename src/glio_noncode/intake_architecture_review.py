"""Deterministic review routing for all held D01 controls."""

from __future__ import annotations

from .intake_architecture_contracts import (
    IntakeArchitectureEvaluation,
    IntakeArchitectureReviewItem,
    IntakeArchitectureReviewQueue,
    IntakeArchitectureScenario,
    IntakeArchitectureState,
    addressed,
)


def build_intake_architecture_review_queue(evaluation: IntakeArchitectureEvaluation) -> IntakeArchitectureReviewQueue:
    items = []
    for ordinal, result in enumerate(
        (item for item in evaluation.results if item.scenario is not IntakeArchitectureScenario.POSITIVE),
        start=1,
    ):
        priority = 1 if "foreign_context" in result.issue_codes else 2 if "malformed_input" in result.issue_codes else 3
        body = {
            "review_id": f"intake-review:{ordinal:03d}",
            "case_id": result.case_id,
            "operation_id": result.operation_id,
            "priority": priority,
            "issue_codes": result.issue_codes,
            "route": "intake-quality-review",
            "state": IntakeArchitectureState.REVIEW,
        }
        items.append(IntakeArchitectureReviewItem(**body, content_address=addressed(body, "intake-review-item")))
    body = {"queue_id": "intake-review-queue-d01", "items": tuple(items), "accepted": len(items) == 48}
    return IntakeArchitectureReviewQueue(**body, content_address=addressed(body, "intake-review-queue"))


def intake_review_csv(queue: IntakeArchitectureReviewQueue) -> str:
    lines = ["review_id,case_id,operation_id,priority,issue_codes,route,state"]
    for item in queue.items:
        lines.append(
            ",".join(
                (
                    item.review_id,
                    item.case_id,
                    item.operation_id,
                    str(item.priority),
                    "+".join(item.issue_codes),
                    item.route,
                    item.state.value,
                )
            )
        )
    return "\n".join(lines) + "\n"


__all__ = ["build_intake_architecture_review_queue", "intake_review_csv"]
