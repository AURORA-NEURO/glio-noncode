"""Deterministic review queue for held structural architecture cases."""

from __future__ import annotations

from .structural_architecture_contracts import (
    StructuralArchitectureEvaluation,
    StructuralArchitectureReviewItem,
    StructuralArchitectureReviewQueue,
    StructuralArchitectureScenario,
    StructuralArchitectureState,
    addressed,
)


def build_structural_architecture_review_queue(
    evaluation: StructuralArchitectureEvaluation,
) -> StructuralArchitectureReviewQueue:
    """Route every non-positive case to a bounded next action."""

    items: list[StructuralArchitectureReviewItem] = []
    for receipt in evaluation.receipts:
        if receipt.expected_state is StructuralArchitectureState.ACCEPTED:
            continue
        reasons = tuple(sorted(set(receipt.observed_issue_codes or ("review_required",))))
        priority = (
            1 if "context_mismatch" in reasons else 2 if "duplicate_identity" in reasons else 3
        )
        action = {
            "context_mismatch": "verify assembly and six-field context before replay",
            "malformed_input": "repair bounded input shape and replay the same operation",
            "duplicate_identity": "adjudicate identity conflict without collapsing observations",
        }.get(reasons[0], "inspect operation receipt and retain review state")
        body = {
            "review_id": f"review:{receipt.case_id}",
            "case_id": receipt.case_id,
            "operation_id": receipt.operation_id,
            "reason_codes": reasons,
            "priority": priority,
            "disposition": "hold",
            "next_action": action,
        }
        items.append(
            StructuralArchitectureReviewItem(
                **body, content_address=addressed(body, "structural-review-item")
            )
        )
    items.sort(key=lambda item: (item.priority, item.review_id))
    accepted = len(items) == evaluation.control_count and all(
        item.disposition == "hold" for item in items
    )
    body = {
        "fixture_id": evaluation.fixture_id,
        "items": items,
        "accepted": accepted,
        "scenario_count": len(items),
    }
    return StructuralArchitectureReviewQueue(
        fixture_id=evaluation.fixture_id,
        items=tuple(items),
        accepted=accepted,
        content_address=addressed(body, "structural-review-queue"),
    )


def _scenario_from_receipt(receipt: object) -> StructuralArchitectureScenario:
    codes = set(getattr(receipt, "observed_issue_codes", ()))
    if "context_mismatch" in codes:
        return StructuralArchitectureScenario.FOREIGN_CONTEXT
    if "malformed_input" in codes:
        return StructuralArchitectureScenario.MALFORMED_INPUT
    return StructuralArchitectureScenario.DUPLICATE_IDENTITY


__all__ = ["build_structural_architecture_review_queue"]
