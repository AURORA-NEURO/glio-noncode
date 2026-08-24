"""D12 control routing and review queue construction."""

from __future__ import annotations

from .cohort_architecture_contracts import (
    CohortArchitectureEvaluation,
    CohortArchitectureReviewItem,
    CohortArchitectureReviewQueue,
    CohortArchitectureScenario,
    CohortArchitectureState,
    addressed,
)


def build_cohort_architecture_review_queue(
    evaluation: CohortArchitectureEvaluation,
) -> CohortArchitectureReviewQueue:
    items = []
    for receipt, execution in zip(evaluation.receipts, evaluation.executions, strict=True):
        if execution.scenario is CohortArchitectureScenario.POSITIVE:
            continue
        blocking = execution.observed_state in {
            CohortArchitectureState.OUT_OF_DOMAIN,
            CohortArchitectureState.INVALID,
        }
        priority = "high" if blocking else "normal"
        reason = ", ".join(execution.observed_issue_codes) or execution.observed_state.value
        body = {
            "case_id": receipt.case_id,
            "operation_id": receipt.operation_id,
            "family": execution.family,
            "scenario": execution.scenario,
            "observed_state": execution.observed_state,
            "priority": priority,
            "blocking": blocking,
            "reason": reason,
            "required_action": (
                "review context, callable or phase coverage, source dependence, "
                "and claim ceiling before release"
            ),
        }
        items.append(
            CohortArchitectureReviewItem(
                **body,
                content_address=addressed(body, "cohort-review"),
            )
        )
    body = {"fixture_id": evaluation.fixture_id, "items": tuple(items)}
    return CohortArchitectureReviewQueue(
        evaluation.fixture_id,
        tuple(items),
        len(items) == 48 and all(item.blocking or item.priority == "normal" for item in items),
        addressed(body, "cohort-review-queue"),
    )


def cohort_architecture_review_summary(
    queue: CohortArchitectureReviewQueue,
) -> dict[str, object]:
    return {
        "fixture_id": queue.fixture_id,
        "accepted": queue.accepted,
        "item_count": len(queue.items),
        "blocking_count": sum(item.blocking for item in queue.items),
        "priority_counts": {
            priority: sum(item.priority == priority for item in queue.items)
            for priority in ("high", "normal")
        },
    }


__all__ = ["build_cohort_architecture_review_queue", "cohort_architecture_review_summary"]
