"""Priority review routing for D04 controls."""

from __future__ import annotations

from .reference_architecture_contracts import (
    ReferenceArchitectureCase,
    ReferenceArchitectureReviewItem,
    ReferenceArchitectureReviewQueue,
    ReferenceArchitectureScenario,
    addressed,
)


def build_reference_architecture_review_queue(
    fixture_id: str, cases: tuple[ReferenceArchitectureCase, ...]
) -> ReferenceArchitectureReviewQueue:
    """Create one explicit review action for every control case."""

    items: list[ReferenceArchitectureReviewItem] = []
    for case in cases:
        if case.scenario is ReferenceArchitectureScenario.POSITIVE:
            continue
        priority = {
            ReferenceArchitectureScenario.IDENTITY_CONFLICT: 1,
            ReferenceArchitectureScenario.FOREIGN_CONTEXT: 2,
            ReferenceArchitectureScenario.MALFORMED_INPUT: 3,
        }[case.scenario]
        action = {
            ReferenceArchitectureScenario.IDENTITY_CONFLICT: (
                "reconcile competing reference identity"
            ),
            ReferenceArchitectureScenario.FOREIGN_CONTEXT: (
                "confirm assembly and context before replay"
            ),
            ReferenceArchitectureScenario.MALFORMED_INPUT: (
                "repair reference payload shape and replay"
            ),
        }[case.scenario]
        body = {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "priority": priority,
            "action": action,
        }
        items.append(
            ReferenceArchitectureReviewItem(
                f"review:{case.case_id}",
                case.case_id,
                case.operation_id,
                case.expected_issue_codes,
                priority,
                "held",
                action,
                addressed(body, "reference-review-item"),
            )
        )
    items.sort(key=lambda item: (item.priority, item.operation_id, item.case_id))
    accepted = len(items) == 48 and len({item.review_id for item in items}) == len(items)
    return ReferenceArchitectureReviewQueue(
        fixture_id,
        tuple(items),
        accepted,
        addressed(
            {"fixture_id": fixture_id, "items": items, "accepted": accepted}, "reference-review"
        ),
    )


def reference_review_priority_counts(queue: ReferenceArchitectureReviewQueue) -> dict[str, int]:
    """Summarize review load by priority."""

    return {
        str(priority): sum(item.priority == priority for item in queue.items)
        for priority in (1, 2, 3)
    }


__all__ = ["build_reference_architecture_review_queue", "reference_review_priority_counts"]
