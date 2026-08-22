"""Capability-to-test validation matrix for the C13-C16 release package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_public_data import (
    ReferenceReleaseFixture,
    ReferenceReleaseOperation,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseValidationRow:
    """One operation validation row with executable evidence labels."""

    capability_id: str
    operation: ReferenceReleaseOperation
    fixture_record_ids: tuple[str, ...]
    expected_states: tuple[str, ...]
    required_test_paths: tuple[str, ...]
    boundary_assertions: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseValidationReport:
    """Validation matrix with row-level acceptance."""

    rows: tuple[ReferenceReleaseValidationRow, ...]
    checks: tuple[tuple[str, bool, str], ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check_id for check_id, passed, _ in self.checks if not passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def build_reference_release_validation_matrix(
    fixture: ReferenceReleaseFixture,
    evaluation: ReferenceReleaseEvaluation,
) -> ReferenceReleaseValidationReport:
    """Build one row per operation from the executed fixture."""

    rows: list[ReferenceReleaseValidationRow] = []
    for operation in ReferenceReleaseOperation:
        executions = tuple(item for item in evaluation.executions if item.operation is operation)
        capability_index = 13 + list(ReferenceReleaseOperation).index(operation)
        body = {
            "capability_id": f"GNC-D04-C{capability_index:02d}",
            "operation": operation,
            "fixture_record_ids": tuple(item.record_id for item in executions),
            "expected_states": tuple(item.state for item in executions),
            "required_test_paths": (
                "public-fixture",
                "positive-path",
                "control-path",
                "replay",
                "quality-gate",
                "cli-smoke",
            ),
            "boundary_assertions": (
                "exact-context",
                "public-aggregate",
                "content-addressed",
                "no-raw-rows",
            ),
        }
        rows.append(
            ReferenceReleaseValidationRow(
                **body, content_address=content_hash(body, prefix="validation-row")
            )
        )
    checks = (
        ("row-count", len(rows) == 4, "four operation rows"),
        (
            "record-closure",
            set(item for row in rows for item in row.fixture_record_ids)
            == {item.record_id for item in fixture.records},
            "all fixture records are mapped",
        ),
        (
            "execution-closure",
            all(len(row.fixture_record_ids) == 4 for row in rows),
            "four executions per operation",
        ),
        (
            "capability-closure",
            tuple(row.capability_id for row in rows)
            == ("GNC-D04-C13", "GNC-D04-C14", "GNC-D04-C15", "GNC-D04-C16"),
            "capability IDs are ordered",
        ),
        (
            "test-depth",
            all(len(row.required_test_paths) >= 6 for row in rows),
            "each row has multiple test paths",
        ),
        (
            "boundary-depth",
            all(len(row.boundary_assertions) >= 4 for row in rows),
            "each row has multiple boundary assertions",
        ),
        (
            "addresses",
            all(row.content_address.startswith("validation-row:") for row in rows),
            "rows are addressed",
        ),
        ("evaluation", evaluation.accepted, "evaluation is accepted"),
        (
            "context",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "all records use exact context",
        ),
        ("states", all(row.expected_states for row in rows), "all rows retain observed states"),
    )
    accepted = all(passed for _, passed, _ in checks)
    body = {"rows": tuple(rows), "checks": checks, "accepted": accepted}
    return ReferenceReleaseValidationReport(
        **body, content_address=content_hash(body, prefix="validation-report")
    )


def validate_reference_release_matrix(report: ReferenceReleaseValidationReport) -> bool:
    """Return whether every validation matrix condition passes."""

    return (
        report.accepted
        and not report.failed_check_ids
        and report.content_address.startswith("validation-report:")
    )


__all__ = [
    "ReferenceReleaseValidationReport",
    "ReferenceReleaseValidationRow",
    "build_reference_release_validation_matrix",
    "validate_reference_release_matrix",
]
