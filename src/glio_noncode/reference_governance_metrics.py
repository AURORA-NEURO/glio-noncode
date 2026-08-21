"""Coverage, issue, and scale metrics for Domain 04 C09–C12 receipts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .reference_governance_fixture_eval import ReferenceGovernanceEvaluationReport
from .reference_governance_public_data import (
    ReferenceGovernanceOperation,
    ReferenceGovernanceRole,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceOperationMetric:
    """Per-operation coverage and state counts."""

    operation: ReferenceGovernanceOperation
    receipt_count: int
    positive_count: int
    control_count: int
    supported_count: int
    review_count: int
    issue_code_counts: tuple[tuple[str, int], ...]
    primary_count_total: int
    secondary_count_total: int
    content_address: str

    @property
    def positive_rate(self) -> float:
        return round(self.positive_count / self.receipt_count, 6) if self.receipt_count else 0.0

    @property
    def review_rate(self) -> float:
        return round(self.review_count / self.receipt_count, 6) if self.receipt_count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "positive_rate": self.positive_rate,
            "review_rate": self.review_rate,
        }


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceMetricsReport:
    """Aggregate metrics with explicit scale and sanitization floors."""

    fixture_id: str
    receipt_count: int
    check_count: int
    positive_count: int
    control_count: int
    supported_count: int
    review_count: int
    operation_metrics: tuple[ReferenceGovernanceOperationMetric, ...]
    issue_code_counts: tuple[tuple[str, int], ...]
    max_summary_keys: int
    sanitized: bool
    content_address: str

    @property
    def accepted(self) -> bool:
        return (
            self.receipt_count == 16
            and self.check_count >= 100
            and self.positive_count == 4
            and self.control_count == 12
            and len(self.operation_metrics) == 4
            and self.sanitized
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def _address(body: Any) -> str:
    return content_hash(body)


def _operation_metric(
    operation: ReferenceGovernanceOperation,
    receipts: tuple[Any, ...],
) -> ReferenceGovernanceOperationMetric:
    issue_codes = Counter(code for receipt in receipts for code in receipt.observed_issue_codes)
    body = {
        "operation": operation,
        "receipt_count": len(receipts),
        "positive_count": sum(item.role is ReferenceGovernanceRole.POSITIVE for item in receipts),
        "control_count": sum(item.role is ReferenceGovernanceRole.CONTROL for item in receipts),
        "supported_count": sum(item.adapter_state == "supported" for item in receipts),
        "review_count": sum(item.adapter_state != "supported" for item in receipts),
        "issue_code_counts": tuple(sorted(issue_codes.items())),
        "primary_count_total": sum(item.primary_count for item in receipts),
        "secondary_count_total": sum(item.secondary_count for item in receipts),
    }
    return ReferenceGovernanceOperationMetric(**body, content_address=_address(body))


def build_reference_governance_metrics(
    evaluation: ReferenceGovernanceEvaluationReport,
) -> ReferenceGovernanceMetricsReport:
    """Build deterministic metrics without copying input payloads."""

    operation_metrics = tuple(
        _operation_metric(
            operation,
            tuple(receipt for receipt in evaluation.receipts if receipt.operation is operation),
        )
        for operation in ReferenceGovernanceOperation
    )
    issue_codes = Counter(
        code for receipt in evaluation.receipts for code in receipt.observed_issue_codes
    )
    max_summary_keys = max((len(receipt.summary) for receipt in evaluation.receipts), default=0)
    sanitized = all(
        not {"records", "restrictions", "queries", "resources"} & set(receipt.summary)
        for receipt in evaluation.receipts
    )
    body = {
        "fixture_id": evaluation.fixture_id,
        "receipt_count": len(evaluation.receipts),
        "check_count": len(evaluation.checks),
        "positive_count": evaluation.positive_count,
        "control_count": evaluation.control_count,
        "supported_count": sum(item.adapter_state == "supported" for item in evaluation.receipts),
        "review_count": sum(item.adapter_state != "supported" for item in evaluation.receipts),
        "operation_metrics": operation_metrics,
        "issue_code_counts": tuple(sorted(issue_codes.items())),
        "max_summary_keys": max_summary_keys,
        "sanitized": sanitized,
    }
    return ReferenceGovernanceMetricsReport(**body, content_address=_address(body))


def verify_reference_governance_metrics(
    report: ReferenceGovernanceMetricsReport,
) -> tuple[str, ...]:
    """Return metric integrity failures."""

    failures: list[str] = []
    if report.content_address != _address(
        {
            key: value
            for key, value in report.to_dict().items()
            if key not in {"accepted", "content_address"}
        }
    ):
        failures.append("metrics-address")
    if len(report.operation_metrics) != 4:
        failures.append("operation-count")
    if sum(metric.receipt_count for metric in report.operation_metrics) != report.receipt_count:
        failures.append("receipt-total")
    if sum(metric.positive_count for metric in report.operation_metrics) != report.positive_count:
        failures.append("positive-total")
    if sum(metric.control_count for metric in report.operation_metrics) != report.control_count:
        failures.append("control-total")
    if any(metric.receipt_count != 4 for metric in report.operation_metrics):
        failures.append("operation-balance")
    if any(
        metric.content_address
        != _address(
            {
                key: value
                for key, value in metric.to_dict().items()
                if key not in {"positive_rate", "review_rate", "content_address"}
            }
        )
        for metric in report.operation_metrics
    ):
        failures.append("operation-address")
    if report.max_summary_keys > 12:
        failures.append("summary-width")
    if not report.sanitized:
        failures.append("sanitization")
    return tuple(failures)


def render_reference_governance_metrics(report: ReferenceGovernanceMetricsReport) -> dict[str, Any]:
    """Return a stable dashboard-shaped metrics view."""

    require_non_empty(report.fixture_id, "metrics fixture_id")
    return {
        "fixture_id": report.fixture_id,
        "totals": {
            "receipts": report.receipt_count,
            "checks": report.check_count,
            "positive": report.positive_count,
            "controls": report.control_count,
            "supported": report.supported_count,
            "review": report.review_count,
        },
        "operations": [
            {
                "operation": metric.operation,
                "receipts": metric.receipt_count,
                "positive_rate": metric.positive_rate,
                "review_rate": metric.review_rate,
                "issues": dict(metric.issue_code_counts),
            }
            for metric in report.operation_metrics
        ],
        "issue_code_counts": dict(report.issue_code_counts),
        "sanitized": report.sanitized,
        "content_address": report.content_address,
    }


__all__ = [
    "ReferenceGovernanceMetricsReport",
    "ReferenceGovernanceOperationMetric",
    "build_reference_governance_metrics",
    "render_reference_governance_metrics",
    "verify_reference_governance_metrics",
]
