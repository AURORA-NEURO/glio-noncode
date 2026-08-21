"""Coverage, state, issue, and scale metrics for Domain 05 C05–C08."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .molecular_atlas_fixture_eval import MolecularAtlasEvaluationReport
from .molecular_atlas_public_data import MolecularAtlasOperation, MolecularAtlasRole
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class MolecularAtlasOperationMetric:
    """Per-operation coverage and state counts."""

    operation: MolecularAtlasOperation
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
class MolecularAtlasMetricsReport:
    """Aggregate scale metrics with explicit sanitization floors."""

    fixture_id: str
    receipt_count: int
    check_count: int
    positive_count: int
    control_count: int
    supported_count: int
    review_count: int
    operation_metrics: tuple[MolecularAtlasOperationMetric, ...]
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
    operation: MolecularAtlasOperation, receipts: tuple[Any, ...]
) -> MolecularAtlasOperationMetric:
    issue_codes = Counter(code for receipt in receipts for code in receipt.observed_issue_codes)
    body = {
        "operation": operation,
        "receipt_count": len(receipts),
        "positive_count": sum(item.role is MolecularAtlasRole.POSITIVE for item in receipts),
        "control_count": sum(item.role is MolecularAtlasRole.CONTROL for item in receipts),
        "supported_count": sum(item.adapter_state == "supported" for item in receipts),
        "review_count": sum(item.adapter_state != "supported" for item in receipts),
        "issue_code_counts": tuple(sorted(issue_codes.items())),
        "primary_count_total": sum(item.primary_count for item in receipts),
        "secondary_count_total": sum(item.secondary_count for item in receipts),
    }
    return MolecularAtlasOperationMetric(**body, content_address=_address(body))


def build_molecular_atlas_metrics(
    evaluation: MolecularAtlasEvaluationReport,
) -> MolecularAtlasMetricsReport:
    """Build deterministic metrics without copying input payloads."""

    operation_metrics = tuple(
        _operation_metric(
            operation,
            tuple(receipt for receipt in evaluation.receipts if receipt.operation is operation),
        )
        for operation in MolecularAtlasOperation
    )
    issue_codes = Counter(
        code for receipt in evaluation.receipts for code in receipt.observed_issue_codes
    )
    max_summary_keys = max((len(receipt.summary) for receipt in evaluation.receipts), default=0)
    sanitized = all(
        not {"records", "restrictions", "queries", "resources", "input_text", "payload"}
        & set(receipt.summary)
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
    return MolecularAtlasMetricsReport(**body, content_address=_address(body))


def verify_molecular_atlas_metrics(report: MolecularAtlasMetricsReport) -> tuple[str, ...]:
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
    for metric in report.operation_metrics:
        expected = {
            key: value
            for key, value in metric.to_dict().items()
            if key not in {"positive_rate", "review_rate", "content_address"}
        }
        if metric.content_address != _address(expected):
            failures.append(f"operation-address:{metric.operation.value}")
    if report.max_summary_keys > 16:
        failures.append("summary-width")
    if not report.sanitized:
        failures.append("sanitization")
    return tuple(failures)


def render_molecular_atlas_metrics(report: MolecularAtlasMetricsReport) -> dict[str, Any]:
    """Return a stable dashboard-shaped view."""

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
    "MolecularAtlasMetricsReport",
    "MolecularAtlasOperationMetric",
    "build_molecular_atlas_metrics",
    "render_molecular_atlas_metrics",
    "verify_molecular_atlas_metrics",
]
