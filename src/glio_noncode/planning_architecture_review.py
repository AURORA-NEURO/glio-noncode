"""Review routing for held D13 planning scenarios."""

from __future__ import annotations

from .planning_architecture_contracts import (
    PlanningArchitectureEvaluation,
    PlanningArchitectureReviewItem,
    PlanningArchitectureReviewQueue,
    PlanningArchitectureState,
    addressed,
)

_BLOCKING_STATES = {
    PlanningArchitectureState.BLOCKED,
    PlanningArchitectureState.REJECTED,
    PlanningArchitectureState.INVALID,
}
_REVIEW_STATES = {
    PlanningArchitectureState.REVIEW,
    PlanningArchitectureState.ABSTAINED,
}


def _priority(state: PlanningArchitectureState) -> tuple[str, bool, str, str]:
    if state in _BLOCKING_STATES:
        return (
            "high",
            True,
            "delegate boundary blocks or rejects the planning input",
            "resolve context, schema, or declared dependency issues before review",
        )
    if state in _REVIEW_STATES:
        return (
            "medium",
            False,
            "delegate retains an incomplete or abstained planning path",
            "inspect the issue codes and supply bounded missing evidence",
        )
    return (
        "low",
        False,
        "delegate result is available for planning review",
        "retain the public receipt and verify downstream assumptions",
    )


def build_planning_architecture_review_queue(
    evaluation: PlanningArchitectureEvaluation,
) -> PlanningArchitectureReviewQueue:
    items: list[PlanningArchitectureReviewItem] = []
    for execution in evaluation.executions:
        priority, blocking, reason, action = _priority(execution.observed_state)
        if (
            execution.scenario.value == "positive"
            and execution.observed_state not in _REVIEW_STATES
        ):
            continue
        body = {
            "case_id": execution.case_id,
            "operation_id": execution.case_id.rsplit("-", 2)[0],
            "family": execution.family,
            "scenario": execution.scenario,
            "observed_state": execution.observed_state,
            "priority": priority,
            "blocking": blocking,
            "reason": reason,
            "required_action": action,
        }
        items.append(
            PlanningArchitectureReviewItem(
                **body,
                content_address=addressed(body, "planning-review-item"),
            )
        )
    items.sort(key=lambda item: (item.blocking is False, item.priority, item.case_id))
    body = {"fixture_id": evaluation.fixture_id, "items": items}
    return PlanningArchitectureReviewQueue(
        evaluation.fixture_id,
        tuple(items),
        all(item.content_address for item in items),
        addressed(body, "planning-review-queue"),
    )


def planning_architecture_review_summary(
    queue: PlanningArchitectureReviewQueue,
) -> dict[str, object]:
    return {
        "fixture_id": queue.fixture_id,
        "accepted": queue.accepted,
        "item_count": len(queue.items),
        "blocking_count": sum(item.blocking for item in queue.items),
        "priority_counts": {
            priority: sum(item.priority == priority for item in queue.items)
            for priority in ("high", "medium", "low")
        },
        "issue_case_ids": [item.case_id for item in queue.items],
    }


__all__ = [
    "build_planning_architecture_review_queue",
    "planning_architecture_review_summary",
]
