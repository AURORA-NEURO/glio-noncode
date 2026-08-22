"""Review rows for Domain 13 planning packages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_metrics import ValidationFrontierMetricsReport
from .validation_frontier_policy import ValidationFrontierPolicyDecision
from .validation_frontier_public_data import ValidationFrontierFixture
from .validation_frontier_release import ValidationFrontierReleaseManifest


@dataclass(frozen=True, slots=True)
class ValidationFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    accepted: bool
    source_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierReviewView:
    fixture_id: str
    rows: tuple[ValidationFrontierReviewRow, ...]
    metric_values: tuple[tuple[str, float], ...]
    policy_values: tuple[tuple[str, str], ...]
    release_state: str
    content_address: str

    def accepted_rows(self) -> tuple[ValidationFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.accepted)

    def issue_rows(self) -> tuple[ValidationFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted_row_count": len(self.accepted_rows()), "issue_row_count": len(self.issue_rows())}


def build_validation_frontier_review_view(fixture: ValidationFrontierFixture, evaluation: ValidationFrontierEvaluation, metrics: ValidationFrontierMetricsReport, policies: tuple[ValidationFrontierPolicyDecision, ...], release: ValidationFrontierReleaseManifest) -> ValidationFrontierReviewView:
    rows = tuple(ValidationFrontierReviewRow(record.record_id, record.operation.value, record.role.value, execution.state, execution.issue_codes, execution.accepted, len(record.source_ids), execution.content_address) for record, execution in zip(fixture.records, evaluation.executions, strict=True))
    body = {"fixture_id": fixture.fixture_id, "rows": rows, "metric_values": tuple((item.metric_id, item.value) for item in metrics.metrics), "policy_values": tuple((item.operation.value, item.decision.value) for item in policies), "release_state": release.state.value}
    return ValidationFrontierReviewView(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierReviewRow", "ValidationFrontierReviewView", "build_validation_frontier_review_view"]
