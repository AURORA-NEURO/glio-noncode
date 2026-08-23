"""Handoff projection for review and downstream release inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture
from .validation_release_frontier_metrics import ValidationReleaseMetrics
from .validation_release_frontier_review_queue import ValidationReleaseReviewQueue


@dataclass(frozen=True, slots=True)
class ValidationReleaseHandoffItem:
    record_id: str
    operation: str
    state: str
    next_action: str
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseHandoff:
    fixture_id: str
    summary: dict[str, Any]
    items: tuple[ValidationReleaseHandoffItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_handoff(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation, metrics: ValidationReleaseMetrics, queue: ValidationReleaseReviewQueue) -> ValidationReleaseHandoff:
    source_map = {item.record_id: item.source_ids for item in fixture.records}
    rows = []
    for execution in evaluation.executions:
        next_action = "research-navigation" if execution.record_id not in {item.record_id for item in queue.items} else "review-control"
        body = {"record_id": execution.record_id, "operation": execution.operation.value, "state": execution.observed_state.value, "next_action": next_action, "source_ids": source_map[execution.record_id]}
        rows.append(ValidationReleaseHandoffItem(**body, content_address=content_hash(body)))
    summary = {"record_count": metrics.record_count, "passed_checks": metrics.passed_checks, "check_count": metrics.check_count, "review_count": queue.review_count, "state_counts": metrics.state_counts}
    return ValidationReleaseHandoff(fixture.fixture_id, summary, tuple(rows), evaluation.accepted, content_hash((summary, tuple(rows))))


__all__ = ["ValidationReleaseHandoff", "ValidationReleaseHandoffItem", "build_validation_release_handoff"]
