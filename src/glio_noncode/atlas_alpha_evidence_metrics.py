"""Operational metrics for the C09-C12 evidence gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_fixture_eval import AtlasAlphaEvidenceEvaluationReport
from .atlas_alpha_evidence_public_data import AtlasAlphaEvidenceOperation, AtlasAlphaEvidenceRole
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceOperationMetric:
    operation: AtlasAlphaEvidenceOperation
    record_count: int
    positive_count: int
    control_count: int
    supported_count: int
    review_count: int
    issue_count: int
    acceptance_rate: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceMetrics:
    fixture_id: str
    total_records: int
    positive_records: int
    control_records: int
    supported_records: int
    review_records: int
    issue_count: int
    check_count: int
    passed_check_count: int
    accepted: bool
    operation_metrics: tuple[AtlasAlphaEvidenceOperationMetric, ...]
    content_address: str

    @property
    def check_pass_rate(self) -> float:
        return self.passed_check_count / self.check_count if self.check_count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"check_pass_rate": self.check_pass_rate}


def compute_atlas_alpha_evidence_metrics(
    evaluation: AtlasAlphaEvidenceEvaluationReport,
) -> AtlasAlphaEvidenceMetrics:
    """Compute reviewable counts without collapsing ambiguous states."""

    operation_metrics: list[AtlasAlphaEvidenceOperationMetric] = []
    for operation in AtlasAlphaEvidenceOperation:
        receipts = tuple(item for item in evaluation.receipts if item.operation is operation)
        supported = sum(item.adapter_state == "supported" for item in receipts)
        review = len(receipts) - supported
        issues = sum(bool(item.observed_issue_codes) for item in receipts)
        body = {
            "operation": operation,
            "record_count": len(receipts),
            "positive_count": sum(
                item.role is AtlasAlphaEvidenceRole.POSITIVE for item in receipts
            ),
            "control_count": sum(item.role is AtlasAlphaEvidenceRole.CONTROL for item in receipts),
            "supported_count": supported,
            "review_count": review,
            "issue_count": issues,
            "acceptance_rate": supported / len(receipts) if receipts else 0.0,
        }
        operation_metrics.append(
            AtlasAlphaEvidenceOperationMetric(**body, content_address=content_hash(body))
        )
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
        "accepted": evaluation.accepted,
        "operation_metrics": operation_metrics,
    }
    return AtlasAlphaEvidenceMetrics(**body, content_address=content_hash(body))


__all__ = [
    "AtlasAlphaEvidenceMetrics",
    "AtlasAlphaEvidenceOperationMetric",
    "compute_atlas_alpha_evidence_metrics",
]
