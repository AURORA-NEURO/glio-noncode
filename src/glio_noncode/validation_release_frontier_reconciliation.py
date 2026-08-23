"""Expected/observed state reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseReconciliation:
    matched_records: tuple[str, ...]
    mismatched_records: tuple[str, ...]
    missing_records: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_validation_release(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation) -> ValidationReleaseReconciliation:
    expected = {item.record_id for item in fixture.records}
    observed = {item.record_id for item in evaluation.executions}
    mismatched = tuple(item.record_id for item in evaluation.executions if item.observed_state != item.expected_state)
    matched = tuple(sorted(expected & observed - set(mismatched)))
    missing = tuple(sorted(expected - observed))
    body = {"matched_records": matched, "mismatched_records": mismatched, "missing_records": missing, "accepted": not mismatched and not missing and expected == observed}
    return ValidationReleaseReconciliation(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseReconciliation", "reconcile_validation_release"]
