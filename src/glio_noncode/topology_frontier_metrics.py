"""Review metrics for Domain 09 topology frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_frontier_fixture_eval import TopologyFrontierEvaluationReport
from .topology_frontier_public_data import TopologyFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyFrontierOperationMetrics:
    operation: TopologyFrontierOperation
    record_count: int
    positive_count: int
    control_count: int
    supported_count: int
    review_count: int
    out_of_domain_count: int
    invalid_count: int
    issue_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierMetrics:
    fixture_id: str
    operation_metrics: tuple[TopologyFrontierOperationMetrics, ...]
    total_records: int
    total_positive: int
    total_controls: int
    total_supported: int
    total_review: int
    total_issues: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def compute_topology_frontier_metrics(evaluation: TopologyFrontierEvaluationReport) -> TopologyFrontierMetrics:
    operation_metrics: list[TopologyFrontierOperationMetrics] = []
    for operation in TopologyFrontierOperation:
        rows = tuple(item for item in evaluation.receipts if item.operation is operation)
        body = {
            "operation": operation,
            "record_count": len(rows),
            "positive_count": sum(item.role.value == "positive" for item in rows),
            "control_count": sum(item.role.value == "control" for item in rows),
            "supported_count": sum(item.adapter_state == "supported" for item in rows),
            "review_count": sum(item.adapter_state == "partial" for item in rows),
            "out_of_domain_count": sum(item.adapter_state == "out_of_domain" for item in rows),
            "invalid_count": sum(item.adapter_state == "invalid" for item in rows),
            "issue_count": sum(len(item.observed_issue_codes) for item in rows),
        }
        operation_metrics.append(TopologyFrontierOperationMetrics(**body, content_address=content_hash(body)))
    body = {
        "fixture_id": evaluation.fixture_id,
        "operation_metrics": operation_metrics,
        "total_records": len(evaluation.receipts),
        "total_positive": evaluation.positive_count,
        "total_controls": evaluation.control_count,
        "total_supported": sum(item.adapter_state == "supported" for item in evaluation.receipts),
        "total_review": sum(item.adapter_state != "supported" for item in evaluation.receipts),
        "total_issues": sum(len(item.observed_issue_codes) for item in evaluation.receipts),
    }
    return TopologyFrontierMetrics(**body, content_address=content_hash(body))


__all__ = [
    "TopologyFrontierMetrics",
    "TopologyFrontierOperationMetrics",
    "compute_topology_frontier_metrics",
]
