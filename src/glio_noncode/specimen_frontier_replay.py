"""Replay integrity checks for Domain 03 C01-C04 fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_frontier_fixture_eval import evaluate_specimen_frontier_fixture
from .specimen_frontier_public_data import SpecimenFrontierFixtureCatalog


@dataclass(frozen=True, slots=True)
class SpecimenFrontierReplayExpectation:
    """Minimum identity and evidence floors for a specimen replay."""

    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    minimum_checks: int = 40
    minimum_positive_records: int = 4
    minimum_control_records: int = 8

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "specimen frontier replay fixture_id")
        require_non_empty(self.context_key, "specimen frontier replay context_key")
        if not self.source_ids:
            raise ValidationError("specimen frontier replay source IDs must not be empty")
        if (
            min(self.minimum_checks, self.minimum_positive_records, self.minimum_control_records)
            < 1
        ):
            raise ValidationError("specimen frontier replay floors must be positive")


@dataclass(frozen=True, slots=True)
class SpecimenFrontierReplayCase:
    """Receipt for one replayed fixture path."""

    path: str
    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    check_count: int
    positive_count: int
    control_count: int
    evaluation_address: str
    passed: bool
    issue_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierReplayReport:
    """Deterministic report across one or more replay paths."""

    fixture_id: str
    required_context_key: str
    cases: tuple[SpecimenFrontierReplayCase, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"case_count": len(self.cases)}


def replay_specimen_frontier_fixtures(
    paths: tuple[str | Path, ...] | list[str | Path],
    *,
    expectation: SpecimenFrontierReplayExpectation,
    required_context_key: str | None = None,
) -> SpecimenFrontierReplayReport:
    """Reload and re-evaluate fixtures against identity and count floors."""

    if not paths:
        raise ValidationError("specimen frontier replay requires at least one path")
    required_context = required_context_key or expectation.context_key
    cases: list[SpecimenFrontierReplayCase] = []
    for path in paths:
        catalog = SpecimenFrontierFixtureCatalog.from_file(path)
        evaluation = evaluate_specimen_frontier_fixture(catalog)
        issues: set[str] = set()
        if catalog.fixture_id != expectation.fixture_id:
            issues.add("fixture_id_mismatch")
        if (
            catalog.context_key != required_context
            or catalog.context_key != expectation.context_key
        ):
            issues.add("context_mismatch")
        if catalog.source_ids != tuple(sorted(expectation.source_ids)):
            issues.add("source_set_mismatch")
        if len(evaluation.checks) < expectation.minimum_checks:
            issues.add("check_floor")
        if len(catalog.positives) < expectation.minimum_positive_records:
            issues.add("positive_floor")
        if len(catalog.controls) < expectation.minimum_control_records:
            issues.add("control_floor")
        addresses = [receipt.output_address for receipt in evaluation.receipts]
        if len(addresses) != len(set(addresses)):
            issues.add("duplicate_output_address")
        if len(catalog.record_ids) != len(set(catalog.record_ids)):
            issues.add("duplicate_record_id")
        if not evaluation.passed:
            issues.add("evaluation_failed")
        cases.append(
            SpecimenFrontierReplayCase(
                path=str(path),
                fixture_id=catalog.fixture_id,
                context_key=catalog.context_key,
                source_ids=catalog.source_ids,
                check_count=len(evaluation.checks),
                positive_count=len(catalog.positives),
                control_count=len(catalog.controls),
                evaluation_address=evaluation.content_address,
                passed=not issues,
                issue_codes=tuple(sorted(issues)),
            )
        )
    passed = bool(cases) and all(case.passed for case in cases)
    body = {
        "fixture_id": expectation.fixture_id,
        "required_context_key": required_context,
        "cases": cases,
        "passed": passed,
    }
    return SpecimenFrontierReplayReport(
        fixture_id=expectation.fixture_id,
        required_context_key=required_context,
        cases=tuple(cases),
        passed=passed,
        content_address=content_hash(body),
    )


__all__ = [
    "SpecimenFrontierReplayCase",
    "SpecimenFrontierReplayExpectation",
    "SpecimenFrontierReplayReport",
    "replay_specimen_frontier_fixtures",
]
