"""Review routing for D05 foreign, malformed, and identity controls."""

from __future__ import annotations

from .atlas_architecture_contracts import (
    AtlasArchitectureCase,
    AtlasArchitectureReviewItem,
    AtlasArchitectureReviewQueue,
    AtlasArchitectureScenario,
    addressed,
)


def build_atlas_architecture_review_queue(
    fixture_id: str,
    cases: tuple[AtlasArchitectureCase, ...],
) -> AtlasArchitectureReviewQueue:
    items: list[AtlasArchitectureReviewItem] = []
    priorities = {
        AtlasArchitectureScenario.IDENTITY_CONFLICT: 1,
        AtlasArchitectureScenario.FOREIGN_CONTEXT: 2,
        AtlasArchitectureScenario.MALFORMED_INPUT: 3,
    }
    for case in cases:
        if case.scenario is AtlasArchitectureScenario.POSITIVE:
            continue
        reason = {
            AtlasArchitectureScenario.IDENTITY_CONFLICT: "identity_conflict",
            AtlasArchitectureScenario.FOREIGN_CONTEXT: "context_mismatch",
            AtlasArchitectureScenario.MALFORMED_INPUT: "malformed_input",
        }[case.scenario]
        action = {
            AtlasArchitectureScenario.IDENTITY_CONFLICT: "reconcile competing atlas identity",
            AtlasArchitectureScenario.FOREIGN_CONTEXT: "confirm context before atlas replay",
            AtlasArchitectureScenario.MALFORMED_INPUT: "repair aggregate payload shape and replay",
        }[case.scenario]
        body = {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "scenario": case.scenario,
            "reason_codes": (reason,),
            "priority": priorities[case.scenario],
            "disposition": "held_for_review",
            "next_action": action,
        }
        items.append(
            AtlasArchitectureReviewItem(
                review_id=f"review:{case.case_id}",
                case_id=case.case_id,
                operation_id=case.operation_id,
                scenario=case.scenario,
                reason_codes=(reason,),
                priority=priorities[case.scenario],
                disposition="held_for_review",
                next_action=action,
                content_address=addressed(body, "atlas-review-item"),
            )
        )
    items.sort(key=lambda item: (item.priority, item.operation_id, item.case_id))
    accepted = len(items) == 48 and len({item.review_id for item in items}) == len(items)
    body = {"fixture_id": fixture_id, "items": items, "accepted": accepted}
    return AtlasArchitectureReviewQueue(
        fixture_id, tuple(items), accepted, addressed(body, "atlas-review-queue")
    )


def atlas_review_priority_counts(queue: AtlasArchitectureReviewQueue) -> dict[str, int]:
    return {
        str(priority): sum(item.priority == priority for item in queue.items)
        for priority in (1, 2, 3)
    }


__all__ = ["atlas_review_priority_counts", "build_atlas_architecture_review_queue"]
