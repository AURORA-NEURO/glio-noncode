"""Operation-level metrics for Domain 08 evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_state_frontier_fixture_eval import CellStateFrontierEvaluationReport
from .cell_state_frontier_public_data import CellStateFrontierOperation, CellStateFrontierRole
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellStateFrontierOperationMetric:
    operation: CellStateFrontierOperation
    record_count: int
    positive_count: int
    control_count: int
    supported_count: int
    review_count: int
    issue_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierMetrics:
    fixture_id: str
    total_records: int
    positive_records: int
    control_records: int
    supported_records: int
    review_records: int
    issue_count: int
    check_count: int
    passed_check_count: int
    operation_metrics: tuple[CellStateFrontierOperationMetric, ...]
    content_address: str

    @property
    def check_pass_rate(self) -> float:
        return self.passed_check_count / self.check_count if self.check_count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"check_pass_rate": self.check_pass_rate}


def compute_cell_state_frontier_metrics(
    evaluation: CellStateFrontierEvaluationReport,
) -> CellStateFrontierMetrics:
    rows: list[CellStateFrontierOperationMetric] = []
    for operation in CellStateFrontierOperation:
        receipts = tuple(item for item in evaluation.receipts if item.operation is operation)
        body = {
            "operation": operation,
            "record_count": len(receipts),
            "positive_count": sum(item.role is CellStateFrontierRole.POSITIVE for item in receipts),
            "control_count": sum(item.role is CellStateFrontierRole.CONTROL for item in receipts),
            "supported_count": sum(item.adapter_state == "supported" for item in receipts),
            "review_count": sum(item.adapter_state != "supported" for item in receipts),
            "issue_count": sum(bool(item.observed_issue_codes) for item in receipts),
        }
        rows.append(CellStateFrontierOperationMetric(**body, content_address=content_hash(body)))
    body = {
        "fixture_id": evaluation.fixture_id,
        "total_records": len(evaluation.receipts),
        "positive_records": evaluation.positive_count,
        "control_records": evaluation.control_count,
        "supported_records": sum(item.adapter_state == "supported" for item in evaluation.receipts),
        "review_records": sum(item.adapter_state != "supported" for item in evaluation.receipts),
        "issue_count": sum(bool(item.observed_issue_codes) for item in evaluation.receipts),
        "check_count": len(evaluation.checks),
        "passed_check_count": sum(item.passed for item in evaluation.checks),
        "operation_metrics": rows,
    }
    return CellStateFrontierMetrics(**body, content_address=content_hash(body))


__all__ = [
    "CellStateFrontierMetrics",
    "CellStateFrontierOperationMetric",
    "compute_cell_state_frontier_metrics",
]
