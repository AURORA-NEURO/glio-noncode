"""Compact release summary projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_metrics import ValidationReleaseMetrics
from .validation_release_frontier_release import ValidationReleaseManifest
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseSummary:
    fixture_id: str
    release_id: str
    accepted: bool
    record_count: int
    check_count: int
    passed_checks: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_summary(evaluation: ValidationReleaseEvaluation, metrics: ValidationReleaseMetrics, release: ValidationReleaseManifest) -> ValidationReleaseSummary:
    body = {"fixture_id": evaluation.fixture_id, "release_id": release.release_id, "accepted": evaluation.accepted and release.accepted, "record_count": metrics.record_count, "check_count": metrics.check_count, "passed_checks": metrics.passed_checks, "state_counts": metrics.state_counts, "issue_counts": metrics.issue_counts}
    return ValidationReleaseSummary(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseSummary", "build_validation_release_summary"]
