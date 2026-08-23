"""Human-review queue, priority, and bounded service-level routing."""

from __future__ import annotations

from .coordination_architecture_contracts import CoordinationExecution, CoordinationReviewItem, CoordinationState, addressed


def _priority(execution: CoordinationExecution) -> int:
    if "contract_mismatch" in execution.issue_codes:
        return 1
    if "foreign_context" in execution.issue_codes:
        return 2
    if "budget_exceeded" in execution.issue_codes:
        return 3
    return 4


def build_coordination_review_queue(executions: tuple[CoordinationExecution, ...]) -> tuple[CoordinationReviewItem, ...]:
    items = []
    for execution in executions:
        if execution.observed_state is CoordinationState.ACCEPTED:
            continue
        priority = _priority(execution)
        body = {
            "review_id": f"review:{execution.case_id}",
            "case_id": execution.case_id,
            "operation_id": execution.operation_id,
            "priority": priority,
            "issue_codes": execution.issue_codes,
            "sla_band": "urgent" if priority == 1 else "standard",
            "state": execution.observed_state,
        }
        items.append(CoordinationReviewItem(**body, content_address=addressed(body, "coordination-review")))
    return tuple(sorted(items, key=lambda item: (item.priority, item.review_id)))


def review_queue_summary(items: tuple[CoordinationReviewItem, ...]) -> dict[str, int]:
    return {
        "total": len(items),
        "urgent": sum(item.sla_band == "urgent" for item in items),
        "standard": sum(item.sla_band == "standard" for item in items),
        "held": sum(item.state is not CoordinationState.ACCEPTED for item in items),
    }


__all__ = ["build_coordination_review_queue", "review_queue_summary"]
