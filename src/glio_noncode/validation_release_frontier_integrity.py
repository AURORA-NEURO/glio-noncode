"""Nested content-address and identity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseIntegrityReport:
    checked_records: int
    checked_executions: int
    failures: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_release_integrity(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation) -> ValidationReleaseIntegrityReport:
    failures = []
    if fixture.content_address != content_hash({"fixture_id": fixture.fixture_id, "fixture_version": fixture.fixture_version, "context_key": fixture.context_key, "evidence_boundary": fixture.evidence_boundary, "sources": fixture.sources, "records": fixture.records}):
        failures.append("fixture-address")
    if any(not item.content_address.startswith("sha256:") for item in fixture.records):
        failures.append("record-address")
    if any(not item.content_address.startswith("sha256:") for item in evaluation.executions):
        failures.append("execution-address")
    body = {"checked_records": len(fixture.records), "checked_executions": len(evaluation.executions), "failures": tuple(failures), "accepted": not failures}
    return ValidationReleaseIntegrityReport(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseIntegrityReport", "evaluate_validation_release_integrity"]
