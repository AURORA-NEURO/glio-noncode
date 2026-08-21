"""Replay and identity checks for beta frontier evidence fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_beta_frontier_fixture_eval import evaluate_specimen_beta_frontier_fixture
from .specimen_beta_frontier_public_data import (
    SPECIMEN_BETA_FRONTIER_CONTROL_FLOOR,
    SPECIMEN_BETA_FRONTIER_OPERATION_FLOOR,
    SpecimenBetaFrontierFixtureCatalog,
    audit_specimen_beta_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierReplayExpectation:
    """Immutable release expectations for one fixture identity."""

    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    minimum_checks: int = 72
    minimum_positive_records: int = SPECIMEN_BETA_FRONTIER_OPERATION_FLOOR
    minimum_control_records: int = SPECIMEN_BETA_FRONTIER_CONTROL_FLOOR

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "beta replay fixture ID")
        require_non_empty(self.context_key, "beta replay context key")
        if not self.source_ids:
            raise ValidationError("beta replay source IDs must not be empty")
        if (
            min(
                self.minimum_checks,
                self.minimum_positive_records,
                self.minimum_control_records,
            )
            < 1
        ):
            raise ValidationError("beta replay floors must be positive")

    @property
    def content_address(self) -> str:
        return content_hash(
            {
                "fixture_id": self.fixture_id,
                "context_key": self.context_key,
                "source_ids": self.source_ids,
                "minimum_checks": self.minimum_checks,
                "minimum_positive_records": self.minimum_positive_records,
                "minimum_control_records": self.minimum_control_records,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"content_address": self.content_address}


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierReplayCase:
    """One replayed fixture path and its issue set."""

    path: str
    fixture_id: str
    passed: bool
    issue_codes: tuple[str, ...]
    evaluation_address: str
    data_audit_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierReplayReport:
    """Replay report for one or more fixture paths."""

    state: str
    expectation_address: str
    cases: tuple[SpecimenBetaFrontierReplayCase, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and not self.issue_codes

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


def replay_specimen_beta_frontier_fixtures(
    paths: list[str | Path] | tuple[str | Path, ...],
    *,
    expectation: SpecimenBetaFrontierReplayExpectation,
) -> SpecimenBetaFrontierReplayReport:
    """Replay fixtures and reject identity, source, floor, or output drift."""

    cases: list[SpecimenBetaFrontierReplayCase] = []
    issues: set[str] = set()
    for path_value in paths:
        path = Path(path_value)
        try:
            catalog = SpecimenBetaFrontierFixtureCatalog.from_file(path)
        except ValidationError:
            issues.add("fixture_load_failure")
            cases.append(
                SpecimenBetaFrontierReplayCase(
                    path=str(path),
                    fixture_id="",
                    passed=False,
                    issue_codes=("fixture_load_failure",),
                    evaluation_address="",
                    data_audit_address="",
                )
            )
            continue
        case_issues: set[str] = set()
        audit = audit_specimen_beta_frontier_fixture(catalog)
        evaluation = evaluate_specimen_beta_frontier_fixture(catalog)
        if catalog.fixture_id != expectation.fixture_id:
            case_issues.add("fixture_id_mismatch")
        if catalog.context_key != expectation.context_key:
            case_issues.add("context_mismatch")
        if catalog.source_ids != tuple(sorted(expectation.source_ids)):
            case_issues.add("source_set_mismatch")
        if len(evaluation.checks) < expectation.minimum_checks:
            case_issues.add("check_floor")
        if len(catalog.positives) < expectation.minimum_positive_records:
            case_issues.add("positive_floor")
        if len(catalog.controls) < expectation.minimum_control_records:
            case_issues.add("control_floor")
        if len(catalog.record_ids) != len(set(catalog.record_ids)):
            case_issues.add("duplicate_record_id")
        output_addresses = [receipt.output_address for receipt in evaluation.receipts]
        if len(output_addresses) != len(set(output_addresses)):
            case_issues.add("duplicate_output_address")
        if not audit.accepted:
            case_issues.add("data_audit_failure")
        if not evaluation.passed:
            case_issues.add("fixture_evaluation_failure")
        issues.update(case_issues)
        cases.append(
            SpecimenBetaFrontierReplayCase(
                path=str(path),
                fixture_id=catalog.fixture_id,
                passed=not case_issues,
                issue_codes=tuple(sorted(case_issues)),
                evaluation_address=evaluation.content_address,
                data_audit_address=audit.content_address,
            )
        )
    state = "accepted" if cases and not issues else "review"
    body = {
        "state": state,
        "expectation_address": expectation.content_address,
        "cases": cases,
        "issue_codes": tuple(sorted(issues)),
    }
    return SpecimenBetaFrontierReplayReport(
        state=state,
        expectation_address=expectation.content_address,
        cases=tuple(cases),
        issue_codes=tuple(sorted(issues)),
        content_address=content_hash(body),
    )


__all__ = [
    "SpecimenBetaFrontierReplayCase",
    "SpecimenBetaFrontierReplayExpectation",
    "SpecimenBetaFrontierReplayReport",
    "replay_specimen_beta_frontier_fixtures",
]
