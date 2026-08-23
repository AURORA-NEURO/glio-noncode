"""Bounded D05 metrics separated by positive and control receipts."""

from __future__ import annotations

from dataclasses import dataclass

from .atlas_architecture_contracts import (
    AtlasArchitectureEvaluation,
    AtlasArchitectureFixture,
    AtlasArchitectureReviewQueue,
    addressed,
)
from .atlas_architecture_review import atlas_review_priority_counts


@dataclass(frozen=True, slots=True)
class AtlasArchitectureMetrics:
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
    family_counts: dict[str, int]
    review_priority_counts: dict[str, int]
    content_address: str


def materialize_atlas_architecture_metrics(
    fixture: AtlasArchitectureFixture,
    evaluation: AtlasArchitectureEvaluation,
    review_queue: AtlasArchitectureReviewQueue,
    validation_cell_count: int,
) -> AtlasArchitectureMetrics:
    positives = tuple(
        item for item in evaluation.receipts if item.expected_state.value == "accepted"
    )
    controls = tuple(item for item in evaluation.receipts if item.expected_state.value == "review")
    body = {
        "fixture_id": fixture.fixture_id,
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": len(positives),
        "control_count": len(controls),
        "accepted_case_count": sum(
            item.observed_state.value == "accepted" for item in evaluation.receipts
        ),
        "review_case_count": sum(
            item.observed_state.value == "review" for item in evaluation.receipts
        ),
        "issue_count": sum(len(item.observed_issue_codes) for item in evaluation.receipts),
        "positive_issue_count": sum(len(item.observed_issue_codes) for item in positives),
        "control_issue_count": sum(len(item.observed_issue_codes) for item in controls),
        "validation_cell_count": validation_cell_count,
        "family_counts": {
            family: sum(item.family.value == family for item in evaluation.receipts)
            for family in (
                "regulatory_atlas",
                "molecular_atlas",
                "atlas_alpha_evidence",
                "frontier_atlas",
            )
        },
        "review_priority_counts": atlas_review_priority_counts(review_queue),
    }
    return AtlasArchitectureMetrics(**body, content_address=addressed(body, "atlas-metrics"))


def atlas_metrics_to_dict(metrics: AtlasArchitectureMetrics) -> dict[str, object]:
    return {field: getattr(metrics, field) for field in metrics.__dataclass_fields__}


__all__ = [
    "AtlasArchitectureMetrics",
    "atlas_metrics_to_dict",
    "materialize_atlas_architecture_metrics",
]
