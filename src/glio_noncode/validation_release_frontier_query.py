"""Deterministic query index over validation-release rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseQueryHit:
    record_id: str
    operation: str
    state: str
    score: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseQueryResult:
    query: str
    hits: tuple[ValidationReleaseQueryHit, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def query_validation_release(evaluation: ValidationReleaseEvaluation, query: str) -> ValidationReleaseQueryResult:
    term = str(query).strip().lower()
    hits = []
    for item in evaluation.executions:
        haystack = " ".join((item.record_id, item.operation.value, item.observed_state.value, *item.issue_codes)).lower()
        if not term or term in haystack:
            body = {"record_id": item.record_id, "operation": item.operation.value, "state": item.observed_state.value, "score": 100 if term and term in item.record_id.lower() else 50}
            hits.append(ValidationReleaseQueryHit(**body, content_address=content_hash(body)))
    hits.sort(key=lambda item: (-item.score, item.record_id))
    return ValidationReleaseQueryResult(term, tuple(hits), content_hash(tuple(hits)))


__all__ = ["ValidationReleaseQueryHit", "ValidationReleaseQueryResult", "query_validation_release"]
