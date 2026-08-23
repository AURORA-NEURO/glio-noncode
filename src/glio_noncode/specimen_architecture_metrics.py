"""Bounded metrics projection for specimen architecture runs."""

from __future__ import annotations

from dataclasses import dataclass

from .specimen_architecture_contracts import (
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureFixture,
    SpecimenArchitectureReviewQueue,
    addressed,
)
from .specimen_architecture_review import review_priority_counts


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureMetrics:
    fixture_id: str
    operation_count: int
    case_count: int
    positive_count: int
    control_count: int
    accepted_case_count: int
    review_case_count: int
    issue_count: int
    validation_cell_count: int
    review_priority_counts: dict[str, int]
    content_address: str


def materialize_specimen_architecture_metrics(
    fixture: SpecimenArchitectureFixture,
    evaluation: SpecimenArchitectureEvaluation,
    review_queue: SpecimenArchitectureReviewQueue,
    validation_cell_count: int,
) -> SpecimenArchitectureMetrics:
    """Build stable counters from receipts and review metadata only."""

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
        "validation_cell_count": validation_cell_count,
        "review_priority_counts": review_priority_counts(review_queue),
    }
    return SpecimenArchitectureMetrics(**body, content_address=addressed(body, "specimen-metrics"))


def metrics_to_dict(metrics: SpecimenArchitectureMetrics) -> dict[str, object]:
    """Return a serialization-safe metrics mapping."""

    return {
        field: getattr(metrics, field)
        for field in metrics.__dataclass_fields__
        if field != "content_address"
    } | {"content_address": metrics.content_address}


__all__ = [
    "SpecimenArchitectureMetrics",
    "materialize_specimen_architecture_metrics",
    "metrics_to_dict",
]
