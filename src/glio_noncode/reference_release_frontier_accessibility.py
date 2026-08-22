"""Accessibility and export-shape checks for release review tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_public_data import ReferenceReleaseFixture
from .reference_release_frontier_views import ReferenceReleaseReviewView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseAccessibilityCheck:
    """One accessible table requirement."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseAccessibilityReport:
    """Review table accessibility result."""

    checks: tuple[ReferenceReleaseAccessibilityCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _check(
    index: int, passed: bool, observed: Any, expected: Any, detail: str
) -> ReferenceReleaseAccessibilityCheck:
    body = {
        "check_id": f"release-accessibility-{index:03d}",
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return ReferenceReleaseAccessibilityCheck(
        **body, content_address=content_hash(body, prefix="accessibility-check")
    )


def evaluate_reference_release_accessibility(
    fixture: ReferenceReleaseFixture,
    evaluation: ReferenceReleaseEvaluation,
    view: ReferenceReleaseReviewView,
) -> ReferenceReleaseAccessibilityReport:
    """Check labels, stable columns, row coverage, and bounded text widths."""

    required_columns = {
        "row_id",
        "record_id",
        "operation",
        "role",
        "state",
        "accepted",
        "issue_codes",
        "source_ids",
        "review_priority",
    }
    checks = (
        _check(1, bool(view.columns), view.columns, "non-empty", "table declares columns"),
        _check(
            2,
            required_columns <= set(view.columns),
            sorted(required_columns - set(view.columns)),
            [],
            "all required review columns are present",
        ),
        _check(
            3,
            len(view.columns) == len(set(view.columns)),
            len(view.columns),
            len(set(view.columns)),
            "columns are unique",
        ),
        _check(
            4,
            len(view.rows) == len(evaluation.executions),
            len(view.rows),
            len(evaluation.executions),
            "one row exists per execution",
        ),
        _check(
            5,
            {row.record_id for row in view.rows}
            == {item.record_id for item in evaluation.executions},
            True,
            True,
            "row IDs close over executions",
        ),
        _check(6, all(row.state for row in view.rows), True, True, "state labels are non-empty"),
        _check(
            7, all(row.operation for row in view.rows), True, True, "operation labels are non-empty"
        ),
        _check(
            8,
            all(len(row.record_id) <= 64 for row in view.rows),
            True,
            True,
            "record labels remain bounded",
        ),
        _check(
            9,
            all(record.context_key == fixture.context_key for record in fixture.records),
            True,
            True,
            "review projection remains context-bound by its release address",
        ),
        _check(
            10,
            all(row.content_address.startswith("review-row:") for row in view.rows),
            True,
            True,
            "row addresses are stable",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"checks": checks, "accepted": accepted}
    return ReferenceReleaseAccessibilityReport(
        **body, content_address=content_hash(body, prefix="accessibility")
    )


__all__ = [
    "ReferenceReleaseAccessibilityCheck",
    "ReferenceReleaseAccessibilityReport",
    "evaluate_reference_release_accessibility",
]
