"""Operational metrics for every D02 operation and validation plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .structural_architecture_contracts import (
    StructuralArchitectureEvaluation,
    StructuralArchitectureFixture,
    StructuralArchitecturePlane,
    addressed,
)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureOperationMetric:
    operation_id: str
    capability_id: str
    family: str
    positive_count: int
    control_count: int
    accepted_count: int
    review_count: int
    issue_count: int
    coverage: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "capability_id": self.capability_id,
            "family": self.family,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
            "accepted_count": self.accepted_count,
            "review_count": self.review_count,
            "issue_count": self.issue_count,
            "coverage": self.coverage,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class StructuralArchitectureMetrics:
    fixture_id: str
    operations: tuple[StructuralArchitectureOperationMetric, ...]
    plane_counts: dict[str, int]
    case_count: int
    accepted_case_count: int
    review_case_count: int
    control_hold_rate: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "operations": [item.to_dict() for item in self.operations],
            "plane_counts": dict(self.plane_counts),
            "case_count": self.case_count,
            "accepted_case_count": self.accepted_case_count,
            "review_case_count": self.review_case_count,
            "control_hold_rate": self.control_hold_rate,
            "content_address": self.content_address,
        }


def measure_structural_architecture(
    fixture: StructuralArchitectureFixture,
    evaluation: StructuralArchitectureEvaluation,
) -> StructuralArchitectureMetrics:
    receipts_by_operation: dict[str, list[Any]] = {}
    for receipt in evaluation.receipts:
        receipts_by_operation.setdefault(receipt.operation_id, []).append(receipt)
    specs = {item.operation_id: item for item in fixture.operations}
    operation_metrics: list[StructuralArchitectureOperationMetric] = []
    for operation_id in fixture.operation_ids:
        receipts = receipts_by_operation.get(operation_id, [])
        positive = sum(item.expected_state.value == "accepted" for item in receipts)
        controls = len(receipts) - positive
        accepted = sum(item.observed_state.value == "accepted" for item in receipts)
        review = len(receipts) - accepted
        issues = sum(len(item.observed_issue_codes) for item in receipts)
        coverage = round(accepted / len(receipts), 6) if receipts else 0.0
        body = {
            "operation_id": operation_id,
            "capability_id": specs[operation_id].capability_id,
            "family": specs[operation_id].family,
            "positive_count": positive,
            "control_count": controls,
            "accepted_count": accepted,
            "review_count": review,
            "issue_count": issues,
            "coverage": coverage,
        }
        operation_metrics.append(
            StructuralArchitectureOperationMetric(
                **body, content_address=addressed(body, "structural-operation-metric")
            )
        )
    plane_counts = {
        plane.value: sum(item.plane.value == plane.value for item in fixture.operations)
        for plane in StructuralArchitecturePlane
    }
    accepted_count = sum(item.observed_state.value == "accepted" for item in evaluation.receipts)
    review_count = len(evaluation.receipts) - accepted_count
    body = {
        "fixture_id": fixture.fixture_id,
        "operations": operation_metrics,
        "plane_counts": plane_counts,
        "case_count": len(evaluation.receipts),
        "accepted_case_count": accepted_count,
        "review_case_count": review_count,
        "control_hold_rate": round(review_count / len(evaluation.receipts), 6)
        if evaluation.receipts
        else 0.0,
    }
    return StructuralArchitectureMetrics(
        **body, content_address=addressed(body, "structural-metrics")
    )


__all__ = [
    "StructuralArchitectureMetrics",
    "StructuralArchitectureOperationMetric",
    "measure_structural_architecture",
]
