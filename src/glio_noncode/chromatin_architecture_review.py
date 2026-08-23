"""Review queue construction for D07 control and uncertainty paths."""

from __future__ import annotations

from .chromatin_architecture_contracts import (
    ChromatinArchitectureCase,
    ChromatinArchitectureReviewItem,
    ChromatinArchitectureReviewQueue,
    ChromatinArchitectureScenario,
    addressed,
)

_PRIORITY = {
    ChromatinArchitectureScenario.IDENTITY_CONFLICT: (
        "blocking",
        True,
        "reconcile source identity and operation joins",
    ),
    ChromatinArchitectureScenario.MALFORMED_INPUT: (
        "high",
        True,
        "repair the public record shape and rerun validation",
    ),
    ChromatinArchitectureScenario.FOREIGN_CONTEXT: (
        "medium",
        False,
        "confirm the context boundary before any reuse",
    ),
}


def build_chromatin_architecture_review_queue(
    fixture_id: str,
    cases: tuple[ChromatinArchitectureCase, ...],
) -> ChromatinArchitectureReviewQueue:
    items = tuple(
        ChromatinArchitectureReviewItem(
            case_id=case.case_id,
            operation_id=case.operation_id,
            scenario=case.scenario,
            priority=_PRIORITY[case.scenario][0],
            blocking=_PRIORITY[case.scenario][1],
            reason=case.description,
            required_action=_PRIORITY[case.scenario][2],
            content_address=addressed(
                {
                    "case_id": case.case_id,
                    "operation_id": case.operation_id,
                    "scenario": case.scenario,
                    "priority": _PRIORITY[case.scenario][0],
                },
                "chromatin-review-item",
            ),
        )
        for case in cases
        if case.scenario is not ChromatinArchitectureScenario.POSITIVE
    )
    body = {"fixture_id": fixture_id, "items": items}
    return ChromatinArchitectureReviewQueue(
        fixture_id=fixture_id,
        items=items,
        accepted=all(item.content_address.startswith("sha256:") for item in items),
        content_address=addressed(body, "chromatin-review"),
    )


__all__ = ["build_chromatin_architecture_review_queue"]
