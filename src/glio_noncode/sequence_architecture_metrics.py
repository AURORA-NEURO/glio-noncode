"""Bounded D06 metrics separated by sequence family and control state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    SequenceArchitectureReviewQueue,
    addressed,
)
from .sequence_architecture_review import sequence_review_priority_counts
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class SequenceArchitectureMetrics:
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
    plane_counts: dict[str, int]
    review_priority_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def materialize_sequence_architecture_metrics(
    fixture: SequenceArchitectureFixture,
    evaluation: SequenceArchitectureEvaluation,
    review_queue: SequenceArchitectureReviewQueue,
    validation_cell_count: int,
) -> SequenceArchitectureMetrics:
    positives = tuple(
        item for item in evaluation.receipts if item.expected_state.value == "accepted"
    )
    controls = tuple(item for item in evaluation.receipts if item.expected_state.value == "review")
    family_counts = {
        family.value: sum(item.family.value == family.value for item in evaluation.receipts)
        for family in sorted(
            {item.family for item in evaluation.receipts}, key=lambda value: value.value
        )
    }
    plane_by_operation = {item.operation_id: item.plane.value for item in fixture.operations}
    plane_counts = {
        plane: sum(plane_by_operation[item.operation_id] == plane for item in evaluation.receipts)
        for plane in sorted(set(plane_by_operation.values()))
    }
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
        "family_counts": family_counts,
        "plane_counts": plane_counts,
        "review_priority_counts": sequence_review_priority_counts(review_queue),
    }
    return SequenceArchitectureMetrics(**body, content_address=addressed(body, "sequence-metrics"))


def sequence_metrics_to_dict(metrics: SequenceArchitectureMetrics) -> dict[str, Any]:
    return metrics.to_dict()


__all__ = [
    "SequenceArchitectureMetrics",
    "materialize_sequence_architecture_metrics",
    "sequence_metrics_to_dict",
]
