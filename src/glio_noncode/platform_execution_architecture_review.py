"""Review routing for held platform and deployment states."""

from __future__ import annotations

from .platform_execution_architecture_contracts import (
    PlatformExecutionEvaluation,
    PlatformExecutionFixture,
    PlatformExecutionReviewItem,
    PlatformExecutionReviewQueue,
    PlatformExecutionScenario,
    PlatformExecutionState,
    addressed,
)
from .platform_execution_architecture_public_data import default_platform_execution_fixture

_SUCCESS = frozenset(
    {
        PlatformExecutionState.READY,
        PlatformExecutionState.COMPATIBLE,
        PlatformExecutionState.ADMITTED,
        PlatformExecutionState.SUPPORTED,
        PlatformExecutionState.SELECTED,
        PlatformExecutionState.COMPLETED,
        PlatformExecutionState.RELEASED,
    }
)


def build_platform_execution_review_queue(
    evaluation: PlatformExecutionEvaluation, fixture: PlatformExecutionFixture | None = None
) -> PlatformExecutionReviewQueue:
    selected = fixture or default_platform_execution_fixture()
    cases = {item.case_id: item for item in selected.cases}
    items = []
    for execution in evaluation.executions:
        case = cases[execution.case_id]
        if (
            case.scenario is PlatformExecutionScenario.POSITIVE
            and execution.observed_state in _SUCCESS
        ):
            continue
        blocking = (
            case.scenario is not PlatformExecutionScenario.POSITIVE
            or execution.observed_state
            in {
                PlatformExecutionState.REJECTED,
                PlatformExecutionState.BLOCKED,
                PlatformExecutionState.DENIED,
                PlatformExecutionState.DRIFT,
                PlatformExecutionState.HOLD,
            }
        )
        body = {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "family": case.family,
            "scenario": case.scenario,
            "observed_state": execution.observed_state,
            "priority": "critical" if blocking else "normal",
            "blocking": blocking,
            "reason": ";".join(execution.observed_issue_codes) or "held state requires review",
            "required_action": "record disposition before release"
            if blocking
            else "confirm or annotate held result",
        }
        items.append(
            PlatformExecutionReviewItem(
                **body, content_address=addressed(body, "platform-execution-review-item")
            )
        )
    body = {"fixture_id": selected.fixture_id, "items": items}
    return PlatformExecutionReviewQueue(
        selected.fixture_id,
        tuple(items),
        all(item.content_address for item in items),
        addressed(body, "platform-execution-review"),
    )


def platform_execution_review_summary(queue: PlatformExecutionReviewQueue) -> dict[str, object]:
    return {
        "fixture_id": queue.fixture_id,
        "item_count": len(queue.items),
        "blocking_count": sum(item.blocking for item in queue.items),
        "accepted": queue.accepted,
    }


__all__ = ["build_platform_execution_review_queue", "platform_execution_review_summary"]
