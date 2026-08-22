"""Coverage, state, issue, and sanitization metrics for release receipts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_public_data import ReferenceReleaseOperation, ReferenceReleaseRole
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceReleaseOperationMetric:
    """Per-operation count and state distribution."""

    operation: ReferenceReleaseOperation
    receipt_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    review_count: int
    blocked_count: int
    drift_count: int
    issue_code_counts: tuple[tuple[str, int], ...]
    output_key_count: int
    content_address: str

    @property
    def positive_rate(self) -> float:
        return round(self.positive_count / self.receipt_count, 6) if self.receipt_count else 0.0

    @property
    def review_rate(self) -> float:
        return (
            round(
                (self.review_count + self.blocked_count + self.drift_count) / self.receipt_count, 6
            )
            if self.receipt_count
            else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "positive_rate": self.positive_rate,
            "review_rate": self.review_rate,
        }


@dataclass(frozen=True, slots=True)
class ReferenceReleaseMetricsReport:
    """Aggregate metrics with explicit fixture and redaction floors."""

    fixture_id: str
    receipt_count: int
    check_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    review_count: int
    blocked_count: int
    drift_count: int
    operation_metrics: tuple[ReferenceReleaseOperationMetric, ...]
    issue_code_counts: tuple[tuple[str, int], ...]
    max_output_keys: int
    sanitized: bool
    content_address: str

    @property
    def accepted(self) -> bool:
        return (
            self.receipt_count == 16
            and self.check_count >= 48
            and self.positive_count == 4
            and self.control_count == 12
            and len(self.operation_metrics) == 4
            and self.sanitized
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def _operation_metric(
    operation: ReferenceReleaseOperation, executions: tuple[Any, ...]
) -> ReferenceReleaseOperationMetric:
    issues = Counter(code for item in executions for code in item.issue_codes)
    body = {
        "operation": operation,
        "receipt_count": len(executions),
        "positive_count": sum(item.role is ReferenceReleaseRole.POSITIVE for item in executions),
        "control_count": sum(item.role is ReferenceReleaseRole.CONTROL for item in executions),
        "accepted_count": sum(item.state in {"accepted", "published"} for item in executions),
        "review_count": sum(item.state == "review" for item in executions),
        "blocked_count": sum(item.state == "blocked" for item in executions),
        "drift_count": sum(item.state == "drift" for item in executions),
        "issue_code_counts": tuple(sorted(issues.items())),
        "output_key_count": max((len(item.output) for item in executions), default=0),
    }
    return ReferenceReleaseOperationMetric(
        **body, content_address=content_hash(body, prefix="operation-metric")
    )


def build_reference_release_metrics(
    evaluation: ReferenceReleaseEvaluation,
) -> ReferenceReleaseMetricsReport:
    """Build sanitized metrics without copying input payload rows."""

    operation_metrics = tuple(
        _operation_metric(
            operation, tuple(item for item in evaluation.executions if item.operation is operation)
        )
        for operation in ReferenceReleaseOperation
    )
    issues = Counter(code for item in evaluation.executions for code in item.issue_codes)
    forbidden = {"records", "previous", "current", "raw_records", "private_keys"}
    sanitized = all(not forbidden & set(item.output) for item in evaluation.executions)
    body = {
        "fixture_id": evaluation.fixture_id,
        "receipt_count": len(evaluation.executions),
        "check_count": len(evaluation.checks),
        "positive_count": evaluation.positive_count,
        "control_count": evaluation.control_count,
        "accepted_count": sum(
            item.state in {"accepted", "published"} for item in evaluation.executions
        ),
        "review_count": sum(item.state == "review" for item in evaluation.executions),
        "blocked_count": sum(item.state == "blocked" for item in evaluation.executions),
        "drift_count": sum(item.state == "drift" for item in evaluation.executions),
        "operation_metrics": operation_metrics,
        "issue_code_counts": tuple(sorted(issues.items())),
        "max_output_keys": max((len(item.output) for item in evaluation.executions), default=0),
        "sanitized": sanitized,
    }
    return ReferenceReleaseMetricsReport(
        **body, content_address=content_hash(body, prefix="release-metrics")
    )


def verify_reference_release_metrics(report: ReferenceReleaseMetricsReport) -> tuple[str, ...]:
    """Return integrity failures for the metrics report."""

    failures: list[str] = []
    if report.receipt_count != sum(item.receipt_count for item in report.operation_metrics):
        failures.append("receipt-total")
    if report.positive_count != sum(item.positive_count for item in report.operation_metrics):
        failures.append("positive-total")
    if report.control_count != sum(item.control_count for item in report.operation_metrics):
        failures.append("control-total")
    if len(report.operation_metrics) != 4:
        failures.append("operation-count")
    if any(item.receipt_count != 4 for item in report.operation_metrics):
        failures.append("operation-balance")
    if any(
        not item.content_address.startswith("operation-metric:")
        for item in report.operation_metrics
    ):
        failures.append("operation-address")
    if report.max_output_keys > 16:
        failures.append("output-width")
    if not report.sanitized:
        failures.append("sanitization")
    return tuple(failures)


def render_reference_release_metrics(report: ReferenceReleaseMetricsReport) -> dict[str, Any]:
    """Return a stable dashboard-shaped projection."""

    require_non_empty(report.fixture_id, "metrics fixture_id")
    return {
        "fixture_id": report.fixture_id,
        "totals": {
            "receipts": report.receipt_count,
            "checks": report.check_count,
            "positive": report.positive_count,
            "controls": report.control_count,
            "accepted": report.accepted_count,
            "review": report.review_count,
            "blocked": report.blocked_count,
            "drift": report.drift_count,
        },
        "operations": [
            {
                "operation": item.operation,
                "receipts": item.receipt_count,
                "positive_rate": item.positive_rate,
                "review_rate": item.review_rate,
                "issues": dict(item.issue_code_counts),
            }
            for item in report.operation_metrics
        ],
        "issue_code_counts": dict(report.issue_code_counts),
        "sanitized": report.sanitized,
        "content_address": report.content_address,
    }


__all__ = [
    "ReferenceReleaseMetricsReport",
    "ReferenceReleaseOperationMetric",
    "build_reference_release_metrics",
    "render_reference_release_metrics",
    "verify_reference_release_metrics",
]
