"""Response bands for reviewable validation-release records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_review_queue import ValidationReleaseReviewQueue


@dataclass(frozen=True, slots=True)
class ValidationReleaseSlaRow:
    record_id: str
    priority: str
    response_hours: int
    escalation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseReviewSla:
    rows: tuple[ValidationReleaseSlaRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_review_sla(queue: ValidationReleaseReviewQueue) -> ValidationReleaseReviewSla:
    rows = []
    for item in queue.items:
        body = {"record_id": item.record_id, "priority": item.priority, "response_hours": 4 if item.priority == "blocking" else 24, "escalation": "release-owner" if item.priority == "blocking" else "domain-review"}
        rows.append(ValidationReleaseSlaRow(**body, content_address=content_hash(body)))
    return ValidationReleaseReviewSla(tuple(rows), all(item.response_hours > 0 for item in rows), content_hash(tuple(rows)))


__all__ = ["ValidationReleaseReviewSla", "ValidationReleaseSlaRow", "build_validation_release_review_sla"]
