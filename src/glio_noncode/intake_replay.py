"""Replay integrity checks for Domain 01 intake evidence fixtures."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .intake_fixture_eval import IntakeFixtureEvaluationReport, IntakeFixtureEvaluator
from .intake_public_data import IntakeDataState, IntakeFixtureCatalog
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class IntakeReplayExpectation:
    """Exact fixture identity and minimum evidence expected during replay."""

    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    minimum_checks: int = 0
    minimum_positive_records: int = 4
    minimum_negative_controls: int = 1

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture_id")
        require_non_empty(self.context_key, "context_key")
        if self.minimum_checks < 1:
            raise ValidationError("minimum_checks must be positive")
        if self.minimum_positive_records < 1:
            raise ValidationError("minimum_positive_records must be positive")
        if self.minimum_negative_controls < 1:
            raise ValidationError("minimum_negative_controls must be positive")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("replay source IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeReplayCaseReceipt:
    """One replayed case plus all identity and evidence mismatches."""

    path: str
    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    state: str
    check_count: int
    positive_record_count: int
    negative_control_count: int
    content_address: str
    integrity_issues: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.integrity_issues and self.state == IntakeDataState.ACCEPTED.value

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        return result


@dataclass(frozen=True, slots=True)
class IntakeReplayReport:
    """Aggregate replay verdict across one or more fixture paths."""

    cases: tuple[IntakeReplayCaseReceipt, ...]
    fixture_ids: tuple[str, ...]
    context_keys: tuple[str, ...]
    source_ids: tuple[str, ...]
    integrity_issues: tuple[str, ...]
    state: IntakeDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == IntakeDataState.ACCEPTED and not self.integrity_issues

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["case_count"] = len(self.cases)
        return result


class IntakeReplayRunner:
    """Replay fixtures and reject context, source, and evidence drift."""

    def __init__(self, evaluator: IntakeFixtureEvaluator | None = None) -> None:
        self.evaluator = evaluator or IntakeFixtureEvaluator()

    def replay(
        self,
        paths: Iterable[str | Path],
        *,
        expectation: IntakeReplayExpectation,
        required_context_key: str | None = None,
    ) -> IntakeReplayReport:
        path_values = tuple(Path(path) for path in paths)
        if not path_values:
            raise ValidationError("at least one intake fixture is required for replay")
        required_context = required_context_key or expectation.context_key
        require_non_empty(required_context, "required_context_key")
        cases: list[IntakeReplayCaseReceipt] = []
        global_issues: list[str] = []
        for path in path_values:
            catalog = IntakeFixtureCatalog.from_file(path)
            report = self.evaluator.evaluate_file(path)
            local = self._case_issues(catalog, report, expectation, required_context)
            receipt = IntakeReplayCaseReceipt(
                str(path),
                report.fixture_id,
                report.context_key,
                report.source_ids,
                report.state.value,
                len(report.checks),
                len(catalog.records),
                len(catalog.controls),
                report.content_address,
                tuple(local),
            )
            cases.append(receipt)
            global_issues.extend(f"{path}:{issue}" for issue in local)
        fixture_ids = tuple(sorted(case.fixture_id for case in cases))
        contexts = tuple(sorted(set(case.context_key for case in cases)))
        source_sets = {case.source_ids for case in cases}
        source_ids = tuple(sorted(set().union(*(set(values) for values in source_sets))))
        if len(fixture_ids) != len(set(fixture_ids)):
            global_issues.append("duplicate_fixture_ids")
        if len({case.content_address for case in cases}) != len(cases):
            global_issues.append("duplicate_case_addresses")
        if len(contexts) != 1:
            global_issues.append("cross_case_context_drift")
        if len(source_sets) != 1:
            global_issues.append("cross_case_source_drift")
        state = IntakeDataState.ACCEPTED if not global_issues else IntakeDataState.REVIEW
        body = {"cases": cases, "issues": global_issues, "expectation": expectation}
        return IntakeReplayReport(
            tuple(cases),
            fixture_ids,
            contexts,
            source_ids,
            tuple(sorted(set(global_issues))),
            state,
            content_hash(body),
        )

    def _case_issues(
        self,
        catalog: IntakeFixtureCatalog,
        report: IntakeFixtureEvaluationReport,
        expectation: IntakeReplayExpectation,
        required_context: str,
    ) -> list[str]:
        issues: list[str] = []
        if report.fixture_id != expectation.fixture_id:
            issues.append("fixture_id_mismatch")
        if report.context_key != required_context or report.context_key != expectation.context_key:
            issues.append("context_mismatch")
        if report.source_ids != tuple(sorted(expectation.source_ids)):
            issues.append("source_set_mismatch")
        if len(report.checks) < expectation.minimum_checks:
            issues.append("check_floor_not_met")
        if len(catalog.records) < expectation.minimum_positive_records:
            issues.append("positive_record_floor_not_met")
        if len(catalog.controls) < expectation.minimum_negative_controls:
            issues.append("negative_control_floor_not_met")
        if report.state != IntakeDataState.ACCEPTED:
            issues.append("fixture_not_accepted")
        record_ids = [record.record_id for record in catalog.records]
        control_ids = [control.control_id for control in catalog.controls]
        if len(record_ids) != len(set(record_ids)):
            issues.append("duplicate_positive_record_ids")
        if len(control_ids) != len(set(control_ids)):
            issues.append("duplicate_negative_control_ids")
        if set(record_ids) & set(control_ids):
            issues.append("positive_negative_identity_collision")
        if not report.passed_check_ids:
            issues.append("no_passed_fixture_checks")
        return issues


def replay_intake_fixtures(
    paths: Iterable[str | Path],
    *,
    expectation: IntakeReplayExpectation,
    required_context_key: str | None = None,
) -> IntakeReplayReport:
    """Replay one or more intake fixtures with the declared expectation."""

    return IntakeReplayRunner().replay(
        paths,
        expectation=expectation,
        required_context_key=required_context_key,
    )


__all__ = [
    "IntakeReplayCaseReceipt",
    "IntakeReplayExpectation",
    "IntakeReplayReport",
    "IntakeReplayRunner",
    "replay_intake_fixtures",
]
