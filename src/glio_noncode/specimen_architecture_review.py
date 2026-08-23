"""Review queue construction for all held specimen controls."""

from __future__ import annotations

from .specimen_architecture_contracts import (
    SpecimenArchitectureCase,
    SpecimenArchitectureReviewItem,
    SpecimenArchitectureReviewQueue,
    SpecimenArchitectureScenario,
    addressed,
)


def build_specimen_architecture_review_queue(
    fixture_id: str,
    cases: tuple[SpecimenArchitectureCase, ...],
) -> SpecimenArchitectureReviewQueue:
    """Route every control to a deterministic next action and priority."""

    items: list[SpecimenArchitectureReviewItem] = []
    for case in cases:
        if case.scenario is SpecimenArchitectureScenario.POSITIVE:
            continue
        priority = {
            SpecimenArchitectureScenario.IDENTITY_CONFLICT: 1,
            SpecimenArchitectureScenario.FOREIGN_CONTEXT: 2,
            SpecimenArchitectureScenario.MALFORMED_INPUT: 3,
        }[case.scenario]
        action = {
            SpecimenArchitectureScenario.IDENTITY_CONFLICT: "reconcile aggregate identity evidence",
            SpecimenArchitectureScenario.FOREIGN_CONTEXT: "confirm reference context before replay",
            SpecimenArchitectureScenario.MALFORMED_INPUT: "repair payload shape and replay",
        }[case.scenario]
        body = {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "priority": priority,
            "action": action,
        }
        items.append(
            SpecimenArchitectureReviewItem(
                review_id=f"review:{case.case_id}",
                case_id=case.case_id,
                operation_id=case.operation_id,
                reason_codes=case.expected_issue_codes,
                priority=priority,
                disposition="held",
                next_action=action,
                content_address=addressed(body, "specimen-review-item"),
            )
        )
    items.sort(key=lambda item: (item.priority, item.operation_id, item.case_id))
    accepted = len(items) == 48 and len({item.review_id for item in items}) == len(items)
    return SpecimenArchitectureReviewQueue(
        fixture_id=fixture_id,
        items=tuple(items),
        accepted=accepted,
        content_address=addressed(
            {"fixture_id": fixture_id, "items": items, "accepted": accepted}, "specimen-review"
        ),
    )


def review_priority_counts(queue: SpecimenArchitectureReviewQueue) -> dict[str, int]:
    """Summarize queue load by priority for release observability."""

    return {
        str(priority): sum(item.priority == priority for item in queue.items)
        for priority in (1, 2, 3)
    }


__all__ = ["build_specimen_architecture_review_queue", "review_priority_counts"]
