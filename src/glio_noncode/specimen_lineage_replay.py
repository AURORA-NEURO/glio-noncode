"""Replay and drift checks for the Domain 03 C09-C12 fixture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable
from .specimen_lineage_fixture_eval import evaluate_specimen_lineage_fixture
from .specimen_lineage_public_data import (
    SpecimenLineageFixtureCatalog,
    audit_specimen_lineage_fixture,
)


@dataclass(frozen=True, slots=True)
class SpecimenLineageReplayExpectation:
    """Minimum stable properties required for one replay run."""

    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    minimum_checks: int
    minimum_positive_records: int
    minimum_control_records: int


@dataclass(frozen=True, slots=True)
class SpecimenLineageReplayEntry:
    """One input-file replay receipt."""

    path: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    audit_address: str
    state: str
    check_count: int
    issue_codes: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageReplayReport:
    """Aggregate replay result with drift diagnostics."""

    expected_fixture_id: str
    expected_context_key: str
    entries: tuple[SpecimenLineageReplayEntry, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return (
            bool(self.entries)
            and not self.issue_codes
            and all(entry.passed for entry in self.entries)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


def replay_specimen_lineage_fixtures(
    paths: list[str | Path] | tuple[str | Path, ...],
    *,
    expectation: SpecimenLineageReplayExpectation,
) -> SpecimenLineageReplayReport:
    """Load and execute fixtures while rejecting identity/context/source drift."""

    entries: list[SpecimenLineageReplayEntry] = []
    issues: set[str] = set()
    for path in paths:
        catalog = SpecimenLineageFixtureCatalog.from_file(path)
        audit = audit_specimen_lineage_fixture(catalog)
        evaluation = evaluate_specimen_lineage_fixture(catalog)
        local_issues = set(audit.issue_codes)
        if catalog.fixture_id != expectation.fixture_id:
            local_issues.add("fixture_id_drift")
        if catalog.context_key != expectation.context_key:
            local_issues.add("context_drift")
        if set(catalog.source_ids) != set(expectation.source_ids):
            local_issues.add("source_set_drift")
        if len(evaluation.checks) < expectation.minimum_checks:
            local_issues.add("check_floor")
        if len(catalog.positives) < expectation.minimum_positive_records:
            local_issues.add("positive_floor")
        if len(catalog.controls) < expectation.minimum_control_records:
            local_issues.add("control_floor")
        if not evaluation.passed:
            local_issues.add("evaluation_failed")
        issues.update(local_issues)
        entries.append(
            SpecimenLineageReplayEntry(
                path=str(path),
                fixture_id=catalog.fixture_id,
                fixture_address=catalog.content_address,
                evaluation_address=evaluation.content_address,
                audit_address=audit.content_address,
                state=evaluation.state,
                check_count=len(evaluation.checks),
                issue_codes=tuple(sorted(local_issues)),
                passed=not local_issues,
            )
        )
    body = {
        "expected_fixture_id": expectation.fixture_id,
        "expected_context_key": expectation.context_key,
        "entries": entries,
        "issue_codes": tuple(sorted(issues)),
    }
    return SpecimenLineageReplayReport(
        expected_fixture_id=expectation.fixture_id,
        expected_context_key=expectation.context_key,
        entries=tuple(entries),
        issue_codes=tuple(sorted(issues)),
        content_address=content_hash(body),
    )


__all__ = [
    "SpecimenLineageReplayEntry",
    "SpecimenLineageReplayExpectation",
    "SpecimenLineageReplayReport",
    "replay_specimen_lineage_fixtures",
]
