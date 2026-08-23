"""Bounded metrics projection for D04 reference composition."""

from __future__ import annotations

from dataclasses import dataclass

from .reference_architecture_contracts import (
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureFixture,
    ReferenceArchitectureReviewQueue,
    addressed,
)
from .reference_architecture_review import reference_review_priority_counts


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureMetrics:
    fixture_id: str
    operation_count: int
    case_count: int
    positive_count: int
    control_count: int
    accepted_case_count: int
    review_case_count: int
    issue_count: int
    positive_issue_count: int
    control_issue_count: int
    validation_cell_count: int
    review_priority_counts: dict[str, int]
    content_address: str


def materialize_reference_architecture_metrics(
    fixture: ReferenceArchitectureFixture,
    evaluation: ReferenceArchitectureEvaluation,
    review_queue: ReferenceArchitectureReviewQueue,
    validation_cell_count: int,
) -> ReferenceArchitectureMetrics:
    positive = tuple(
        item for item in evaluation.receipts if item.expected_state.value == "accepted"
    )
    controls = tuple(item for item in evaluation.receipts if item.expected_state.value == "review")
    body = {
        "fixture_id": fixture.fixture_id,
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": len(positive),
        "control_count": len(controls),
        "accepted_case_count": sum(
            item.observed_state.value == "accepted" for item in evaluation.receipts
        ),
        "review_case_count": sum(
            item.observed_state.value == "review" for item in evaluation.receipts
        ),
        "issue_count": sum(len(item.observed_issue_codes) for item in evaluation.receipts),
        "positive_issue_count": sum(len(item.observed_issue_codes) for item in positive),
        "control_issue_count": sum(len(item.observed_issue_codes) for item in controls),
        "validation_cell_count": validation_cell_count,
        "review_priority_counts": reference_review_priority_counts(review_queue),
    }
    return ReferenceArchitectureMetrics(
        **body, content_address=addressed(body, "reference-metrics")
    )


def reference_metrics_to_dict(metrics: ReferenceArchitectureMetrics) -> dict[str, object]:
    """Return a stable JSON projection."""

    return {field: getattr(metrics, field) for field in metrics.__dataclass_fields__}


__all__ = [
    "ReferenceArchitectureMetrics",
    "materialize_reference_architecture_metrics",
    "reference_metrics_to_dict",
]
