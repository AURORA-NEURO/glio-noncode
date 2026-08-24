"""Review routing for held workbench states and explicit controls."""

from __future__ import annotations

from .workbench_architecture_contracts import (
    WorkbenchArchitectureEvaluation,
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureReviewItem,
    WorkbenchArchitectureReviewQueue,
    WorkbenchArchitectureScenario,
    WorkbenchArchitectureState,
    addressed,
)
from .workbench_architecture_public_data import default_workbench_architecture_fixture

_SUCCESS_STATES = frozenset(
    {
        WorkbenchArchitectureState.SUPPORTED,
        WorkbenchArchitectureState.COMPLETE,
        WorkbenchArchitectureState.ALLOWED,
        WorkbenchArchitectureState.VERIFIED,
        WorkbenchArchitectureState.REVIEWED,
        WorkbenchArchitectureState.EXPORTED,
        WorkbenchArchitectureState.SEARCHED,
        WorkbenchArchitectureState.PASSED,
    }
)


def build_workbench_architecture_review_queue(
    evaluation: WorkbenchArchitectureEvaluation, fixture: WorkbenchArchitectureFixture | None = None
) -> WorkbenchArchitectureReviewQueue:
    selected = fixture or default_workbench_architecture_fixture()
    cases = {item.case_id: item for item in selected.cases}
    items = []
    for execution in evaluation.executions:
        case = cases[execution.case_id]
        held = (
            case.scenario is not WorkbenchArchitectureScenario.POSITIVE
            or execution.observed_state not in _SUCCESS_STATES
        )
        if not held:
            continue
        blocking = (
            case.scenario is not WorkbenchArchitectureScenario.POSITIVE
            or execution.observed_state
            in {
                WorkbenchArchitectureState.INVALID,
                WorkbenchArchitectureState.BLOCKED,
                WorkbenchArchitectureState.REJECTED,
                WorkbenchArchitectureState.OUT_OF_DOMAIN,
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
            "reason": ";".join(execution.observed_issue_codes)
            or "held workbench state requires review",
            "required_action": "record disposition before release"
            if blocking
            else "confirm or annotate held result",
        }
        items.append(
            WorkbenchArchitectureReviewItem(
                **body, content_address=addressed(body, "workbench-architecture-review-item")
            )
        )
    body = {"fixture_id": selected.fixture_id, "items": items}
    return WorkbenchArchitectureReviewQueue(
        selected.fixture_id,
        tuple(items),
        all(item.content_address for item in items),
        addressed(body, "workbench-architecture-review"),
    )


def workbench_architecture_review_summary(
    queue: WorkbenchArchitectureReviewQueue,
) -> dict[str, object]:
    return {
        "fixture_id": queue.fixture_id,
        "item_count": len(queue.items),
        "blocking_count": sum(item.blocking for item in queue.items),
        "critical_count": sum(item.priority == "critical" for item in queue.items),
        "families": sorted({item.family.value for item in queue.items}),
        "accepted": queue.accepted,
    }


__all__ = ["build_workbench_architecture_review_queue", "workbench_architecture_review_summary"]
