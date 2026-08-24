"""Review routing for held evidence states and explicit controls."""

from __future__ import annotations

from .evidence_architecture_contracts import (
    EvidenceArchitectureEvaluation,
    EvidenceArchitectureFixture,
    EvidenceArchitectureReviewItem,
    EvidenceArchitectureReviewQueue,
    EvidenceArchitectureScenario,
    EvidenceArchitectureState,
    addressed,
)
from .evidence_architecture_public_data import default_evidence_architecture_fixture

_SUCCESS_STATES = frozenset(
    {
        EvidenceArchitectureState.SUPPORTED,
        EvidenceArchitectureState.CLEAR,
        EvidenceArchitectureState.ADJUDICATED,
        EvidenceArchitectureState.APPROVED,
        EvidenceArchitectureState.RECLASSIFIED,
        EvidenceArchitectureState.SUPERSEDED,
        EvidenceArchitectureState.BUNDLED,
        EvidenceArchitectureState.SIGNED,
    }
)


def build_evidence_architecture_review_queue(
    evaluation: EvidenceArchitectureEvaluation,
    fixture: EvidenceArchitectureFixture | None = None,
) -> EvidenceArchitectureReviewQueue:
    selected = fixture or default_evidence_architecture_fixture()
    cases = {item.case_id: item for item in selected.cases}
    items: list[EvidenceArchitectureReviewItem] = []
    for execution in evaluation.executions:
        case = cases[execution.case_id]
        held = (
            case.scenario is not EvidenceArchitectureScenario.POSITIVE
            or execution.observed_state not in _SUCCESS_STATES
        )
        if not held:
            continue
        blocking = (
            case.scenario is not EvidenceArchitectureScenario.POSITIVE
            or execution.observed_state
            in {
                EvidenceArchitectureState.INVALID,
                EvidenceArchitectureState.CONTRADICTORY,
                EvidenceArchitectureState.BLOCKED,
                EvidenceArchitectureState.REJECTED,
            }
        )
        priority = "critical" if blocking else "normal"
        body = {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "family": case.family,
            "scenario": case.scenario,
            "observed_state": execution.observed_state,
            "priority": priority,
            "blocking": blocking,
            "reason": ";".join(execution.observed_issue_codes)
            or "held evidence state requires review",
            "required_action": "record disposition before release"
            if blocking
            else "confirm or annotate held result",
        }
        items.append(
            EvidenceArchitectureReviewItem(
                **body,
                content_address=addressed(body, "evidence-architecture-review-item"),
            )
        )
    body = {"fixture_id": selected.fixture_id, "items": items}
    return EvidenceArchitectureReviewQueue(
        selected.fixture_id,
        tuple(items),
        all(item.content_address for item in items),
        addressed(body, "evidence-architecture-review"),
    )


def evidence_architecture_review_summary(
    queue: EvidenceArchitectureReviewQueue,
) -> dict[str, object]:
    return {
        "fixture_id": queue.fixture_id,
        "item_count": len(queue.items),
        "blocking_count": sum(item.blocking for item in queue.items),
        "critical_count": sum(item.priority == "critical" for item in queue.items),
        "families": sorted({item.family.value for item in queue.items}),
        "accepted": queue.accepted,
    }


__all__ = ["build_evidence_architecture_review_queue", "evidence_architecture_review_summary"]
