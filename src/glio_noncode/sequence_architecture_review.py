"""Review queue construction for D06 held controls."""

from __future__ import annotations

from .sequence_architecture_contracts import (
    SequenceArchitectureCase,
    SequenceArchitectureReviewItem,
    SequenceArchitectureReviewQueue,
    SequenceArchitectureScenario,
    addressed,
)


def build_sequence_architecture_review_queue(
    fixture_id: str, cases: tuple[SequenceArchitectureCase, ...]
) -> SequenceArchitectureReviewQueue:
    items = tuple(
        _item(case) for case in cases if case.scenario is not SequenceArchitectureScenario.POSITIVE
    )
    body = {"fixture_id": fixture_id, "items": items}
    return SequenceArchitectureReviewQueue(
        fixture_id=fixture_id,
        items=items,
        accepted=len(items) == 48,
        content_address=addressed(body, "sequence-review-queue"),
    )


def sequence_review_priority_counts(queue: SequenceArchitectureReviewQueue) -> dict[str, int]:
    return {
        str(priority): sum(item.priority == priority for item in queue.items)
        for priority in sorted({item.priority for item in queue.items})
    }


def _item(case: SequenceArchitectureCase) -> SequenceArchitectureReviewItem:
    if case.scenario is SequenceArchitectureScenario.IDENTITY_CONFLICT:
        priority, reasons, action = (
            1,
            ("identity_conflict",),
            "reconcile declared operation and record identity",
        )
    elif case.scenario is SequenceArchitectureScenario.FOREIGN_CONTEXT:
        priority, reasons, action = (
            2,
            ("context_mismatch",),
            "confirm sequence context before any delegation",
        )
    else:
        priority, reasons, action = (
            3,
            ("malformed_input",),
            "repair payload shape and rerun validation",
        )
    body = {
        "case_id": case.case_id,
        "operation_id": case.operation_id,
        "scenario": case.scenario,
        "priority": priority,
        "reason_codes": reasons,
        "next_action": action,
    }
    return SequenceArchitectureReviewItem(
        review_id=f"review-{case.case_id}",
        case_id=case.case_id,
        operation_id=case.operation_id,
        scenario=case.scenario,
        reason_codes=reasons,
        priority=priority,
        disposition="held",
        next_action=action,
        content_address=addressed(body, "sequence-review-item"),
    )


__all__ = ["build_sequence_architecture_review_queue", "sequence_review_priority_counts"]
