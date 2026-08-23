"""Review-oriented row and field projections."""

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    review_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReviewView:
    rows: tuple[ValidationBetaFrontierReviewRow, ...]
    visible_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_review_view(evaluation: ValidationBetaFrontierEvaluation) -> ValidationBetaFrontierReviewView:
    rows = tuple(ValidationBetaFrontierReviewRow(item.record_id, item.operation.value, "positive" if item.record_id.endswith("POS-001") else "control", item.observed_state, item.observed_issue_codes, "publish bounded review" if item.accepted and item.record_id.endswith("POS-001") else "inspect boundary", content_hash({"record_id": item.record_id, "state": item.observed_state}, prefix="validation-beta-view-row")) for item in evaluation.rows)
    fields = ("record_id", "operation", "role", "state", "issue_codes", "review_action", "content_address")
    return ValidationBetaFrontierReviewView(rows, fields, len(rows) == 32 and len(fields) == 7, content_hash({"rows": rows, "fields": fields}, prefix="validation-beta-review-view"))


__all__ = ["ValidationBetaFrontierReviewRow", "ValidationBetaFrontierReviewView", "build_validation_beta_frontier_review_view"]
