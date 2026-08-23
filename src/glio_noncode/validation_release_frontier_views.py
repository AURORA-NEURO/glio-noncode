"""Stable review-view projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseViewEntry:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    score: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseView:
    entries: tuple[ValidationReleaseViewEntry, ...]
    columns: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_view(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseView:
    entries = []
    for item in evaluation.executions:
        body = {"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "state": item.observed_state.value, "issue_codes": item.issue_codes, "score": 100 if item.observed_state.value in {"ready", "packaged", "updated"} else 50}
        entries.append(ValidationReleaseViewEntry(**body, content_address=content_hash(body)))
    return ValidationReleaseView(tuple(entries), ("record_id", "operation", "role", "state", "issue_codes", "score"), content_hash(tuple(entries)))


__all__ = ["ValidationReleaseView", "ValidationReleaseViewEntry", "build_validation_release_view"]
