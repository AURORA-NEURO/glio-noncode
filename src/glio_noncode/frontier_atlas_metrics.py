"""Operational metrics for C13-C16 frontier atlas receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frontier_atlas_fixture_eval import FrontierAtlasEvaluationReport
from .frontier_atlas_public_data import FrontierAtlasOperation, FrontierAtlasRole
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FrontierAtlasOperationMetric:
    operation: FrontierAtlasOperation
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    published_count: int
    review_count: int
    issue_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasMetrics:
    fixture_id: str
    total_records: int
    positive_records: int
    control_records: int
    accepted_records: int
    published_records: int
    review_records: int
    issue_count: int
    check_count: int
    passed_check_count: int
    operation_metrics: tuple[FrontierAtlasOperationMetric, ...]
    content_address: str

    @property
    def check_pass_rate(self) -> float:
        return self.passed_check_count / self.check_count if self.check_count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"check_pass_rate": self.check_pass_rate}


def compute_frontier_atlas_metrics(
    evaluation: FrontierAtlasEvaluationReport,
) -> FrontierAtlasMetrics:
    operation_metrics: list[FrontierAtlasOperationMetric] = []
    for operation in FrontierAtlasOperation:
        receipts = tuple(item for item in evaluation.receipts if item.operation is operation)
        body = {
            "operation": operation,
            "record_count": len(receipts),
            "positive_count": sum(item.role is FrontierAtlasRole.POSITIVE for item in receipts),
            "control_count": sum(item.role is FrontierAtlasRole.CONTROL for item in receipts),
            "accepted_count": sum(item.adapter_state == "accepted" for item in receipts),
            "published_count": sum(item.adapter_state == "published" for item in receipts),
            "review_count": sum(
                item.adapter_state not in {"accepted", "published"} for item in receipts
            ),
            "issue_count": sum(bool(item.observed_issue_codes) for item in receipts),
        }
        operation_metrics.append(
            FrontierAtlasOperationMetric(**body, content_address=content_hash(body))
        )
    body = {
        "fixture_id": evaluation.fixture_id,
        "total_records": len(evaluation.receipts),
        "positive_records": evaluation.positive_count,
        "control_records": evaluation.control_count,
        "accepted_records": sum(item.adapter_state == "accepted" for item in evaluation.receipts),
        "published_records": sum(item.adapter_state == "published" for item in evaluation.receipts),
        "review_records": sum(
            item.adapter_state not in {"accepted", "published"} for item in evaluation.receipts
        ),
        "issue_count": sum(bool(item.observed_issue_codes) for item in evaluation.receipts),
        "check_count": len(evaluation.checks),
        "passed_check_count": sum(item.passed for item in evaluation.checks),
        "operation_metrics": operation_metrics,
    }
    return FrontierAtlasMetrics(**body, content_address=content_hash(body))


__all__ = ["FrontierAtlasMetrics", "FrontierAtlasOperationMetric", "compute_frontier_atlas_metrics"]
