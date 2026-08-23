"""Hard invariants for identity, state, address, and control coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseInvariantReport:
    checks: dict[str, bool]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_release_invariants(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation) -> ValidationReleaseInvariantReport:
    checks = {"unique_record_ids": len({item.record_id for item in fixture.records}) == len(fixture.records), "same_record_count": len(fixture.records) == len(evaluation.executions), "positive_count": len(fixture.positive_records) == 4, "control_count": len(fixture.control_records) == 12, "content_addresses": all(item.content_address.startswith("sha256:") for item in evaluation.executions), "no_positive_issue": all(not item.issue_codes for item in evaluation.executions if item.role.value == "positive")}
    return ValidationReleaseInvariantReport(checks, all(checks.values()), content_hash(checks))


def assert_validation_release_invariants(report: ValidationReleaseInvariantReport) -> None:
    if not report.accepted:
        raise AssertionError(report.checks)


__all__ = ["ValidationReleaseInvariantReport", "assert_validation_release_invariants", "evaluate_validation_release_invariants"]
