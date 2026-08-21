"""Replay integrity checks for public aggregate Domain 01 identity fixtures."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .identity_fixture_eval import IdentityFixtureEvaluator
from .identity_public_data import IdentityDataState
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class IdentityReplayExpectation:
    """Minimum replay contract for a group of identity fixture files."""

    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    min_check_count: int = 37
    min_positive_count: int = 4
    min_negative_control_count: int = 8

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture_id")
        require_non_empty(self.context_key, "context_key")
        if self.min_check_count < 1:
            raise ValidationError("identity replay min_check_count must be positive")
        if self.min_positive_count < 1:
            raise ValidationError("identity replay min_positive_count must be positive")
        if self.min_negative_control_count < 1:
            raise ValidationError("identity replay min_negative_control_count must be positive")


@dataclass(frozen=True, slots=True)
class IdentityReplayCaseReceipt:
    """Stable receipt for one replayed fixture path."""

    path: str
    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    state: IdentityDataState
    passed: bool
    check_count: int
    positive_count: int
    negative_control_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IdentityReplayReport:
    """Replay result across one or more identity fixture files."""

    expectation: IdentityReplayExpectation
    cases: tuple[IdentityReplayCaseReceipt, ...]
    duplicate_fixture_ids: tuple[str, ...]
    duplicate_public_identities: tuple[str, ...]
    context_mismatch_paths: tuple[str, ...]
    source_mismatch_paths: tuple[str, ...]
    failed_reasons: tuple[str, ...]
    state: IdentityDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == IdentityDataState.ACCEPTED and not self.failed_reasons

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["case_count"] = len(self.cases)
        return result


class IdentityReplayRunner:
    """Replay identity fixtures and compare their stable public boundaries."""

    def __init__(self, evaluator: IdentityFixtureEvaluator | None = None) -> None:
        self.evaluator = evaluator or IdentityFixtureEvaluator()

    def replay(
        self,
        paths: Sequence[str | Path],
        *,
        expectation: IdentityReplayExpectation,
    ) -> IdentityReplayReport:
        if not paths:
            raise ValidationError("identity replay requires at least one fixture path")
        cases: list[IdentityReplayCaseReceipt] = []
        fixture_ids: list[str] = []
        public_ids: list[str] = []
        contexts: list[str] = []
        sources_by_path: dict[str, tuple[str, ...]] = {}
        failed: list[str] = []
        for raw_path in paths:
            path = str(Path(raw_path))
            report = self.evaluator.evaluate_file(path)
            catalog = self.evaluator.validate_fixture(self.evaluator.load_file(path))
            fixture_ids.append(report.fixture_id)
            contexts.append(report.context_key)
            source_ids = tuple(sorted(report.source_ids))
            sources_by_path[path] = source_ids
            public_ids.extend(record.public_identifier for record in catalog.records)
            public_ids.extend(control.public_identifier for control in catalog.controls)
            case_passed = report.passed
            reasons: list[str] = []
            if report.fixture_id != expectation.fixture_id:
                reasons.append(f"{path}: fixture ID differs from replay expectation")
            if report.context_key != expectation.context_key:
                reasons.append(f"{path}: context differs from replay expectation")
            if source_ids != tuple(sorted(expectation.source_ids)):
                reasons.append(f"{path}: source receipt set differs from replay expectation")
            if report.state != IdentityDataState.ACCEPTED:
                reasons.append(f"{path}: fixture evaluation is not accepted")
            if len(report.checks) < expectation.min_check_count:
                reasons.append(f"{path}: check count is below replay floor")
            if len(report.positive_reports) < expectation.min_positive_count:
                reasons.append(f"{path}: positive record count is below replay floor")
            if len(report.negative_reports) < expectation.min_negative_control_count:
                reasons.append(f"{path}: negative control count is below replay floor")
            if reasons:
                case_passed = False
                failed.extend(reasons)
            cases.append(
                IdentityReplayCaseReceipt(
                    path,
                    report.fixture_id,
                    report.context_key,
                    source_ids,
                    report.state,
                    case_passed,
                    len(report.checks),
                    len(report.positive_reports),
                    len(report.negative_reports),
                    report.content_address,
                )
            )
        duplicate_fixture_ids = _duplicates(fixture_ids)
        duplicate_public_identities = _duplicates(public_ids)
        if duplicate_fixture_ids:
            failed.append("fixture IDs must be unique across replay cases")
        if duplicate_public_identities and len(cases) > 1:
            failed.append("public identities must not be duplicated across distinct replay cases")
        context_mismatch_paths = tuple(
            case.path for case in cases if case.context_key != expectation.context_key
        )
        source_mismatch_paths = tuple(
            path
            for path, source_ids in sources_by_path.items()
            if source_ids != tuple(sorted(expectation.source_ids))
        )
        if context_mismatch_paths:
            failed.append("replay cases must share one exact context")
        if source_mismatch_paths:
            failed.append("replay cases must share one exact source receipt set")
        state = (
            IdentityDataState.ACCEPTED
            if not failed and all(case.passed for case in cases)
            else IdentityDataState.REVIEW
        )
        body = {
            "expectation": expectation,
            "cases": cases,
            "duplicate_fixture_ids": duplicate_fixture_ids,
            "duplicate_public_identities": duplicate_public_identities,
            "context_mismatch_paths": context_mismatch_paths,
            "source_mismatch_paths": source_mismatch_paths,
            "failed_reasons": tuple(dict.fromkeys(failed)),
        }
        return IdentityReplayReport(
            expectation,
            tuple(cases),
            duplicate_fixture_ids,
            duplicate_public_identities,
            context_mismatch_paths,
            source_mismatch_paths,
            tuple(dict.fromkeys(failed)),
            state,
            content_hash(body),
        )


def _duplicates(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(value for value in set(values) if values.count(value) > 1))


def replay_identity_fixtures(
    paths: Sequence[str | Path],
    *,
    expectation: IdentityReplayExpectation,
) -> IdentityReplayReport:
    """Convenience function for deterministic identity replay."""

    return IdentityReplayRunner().replay(paths, expectation=expectation)


__all__ = [
    "IdentityReplayCaseReceipt",
    "IdentityReplayExpectation",
    "IdentityReplayReport",
    "IdentityReplayRunner",
    "replay_identity_fixtures",
]
