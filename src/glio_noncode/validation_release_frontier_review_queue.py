"""Bounded review queue that keeps every non-ready control visible."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseReviewItem:
    record_id: str
    operation: str
    state: str
    issue_codes: tuple[str, ...]
    priority: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseReviewQueue:
    items: tuple[ValidationReleaseReviewItem, ...]
    ready_count: int
    review_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_review_queue(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseReviewQueue:
    rows = []
    for execution in evaluation.executions:
        if execution.observed_state.value in {"ready", "packaged", "updated"}:
            continue
        priority = "blocking" if execution.observed_state.value in {"blocked", "rejected"} else "review"
        body = {"record_id": execution.record_id, "operation": execution.operation.value, "state": execution.observed_state.value, "issue_codes": execution.issue_codes, "priority": priority}
        rows.append(ValidationReleaseReviewItem(**body, content_address=content_hash(body)))
    rows.sort(key=lambda item: (0 if item.priority == "blocking" else 1, item.record_id))
    return ValidationReleaseReviewQueue(tuple(rows), sum(item.observed_state.value in {"ready", "packaged", "updated"} for item in evaluation.executions), len(rows), evaluation.accepted, content_hash(tuple(rows)))


__all__ = ["ValidationReleaseReviewItem", "ValidationReleaseReviewQueue", "build_validation_release_review_queue"]
