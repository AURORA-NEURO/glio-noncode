"""Replay expectations for the C13-C16 public aggregate fixture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .specimen_preanalytic_fixture_eval import (
    SpecimenPreanalyticEvaluationReport,
    evaluate_specimen_preanalytic_fixture,
)
from .specimen_preanalytic_public_data import SpecimenPreanalyticFixtureCatalog


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticReplayExpectation:
    fixture_id: str
    required_context_key: str
    minimum_receipts: int
    minimum_checks: int
    positive_count: int
    control_count: int

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "replay fixture ID")
        require_non_empty(self.required_context_key, "replay context key")
        if (
            min(self.minimum_receipts, self.minimum_checks, self.positive_count, self.control_count)
            < 1
        ):
            raise ValueError("replay floors must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticReplayEntry:
    path: str
    fixture_id: str
    state: str
    passed: bool
    failed_expectations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticReplayReport:
    expectation: SpecimenPreanalyticReplayExpectation
    entries: tuple[SpecimenPreanalyticReplayEntry, ...]
    state: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(entry.passed for entry in self.entries)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


def default_specimen_preanalytic_expectation(
    catalog: SpecimenPreanalyticFixtureCatalog,
) -> SpecimenPreanalyticReplayExpectation:
    return SpecimenPreanalyticReplayExpectation(
        fixture_id=catalog.fixture_id,
        required_context_key=catalog.context_key,
        minimum_receipts=12,
        minimum_checks=120,
        positive_count=4,
        control_count=8,
    )


def replay_specimen_preanalytic_fixture(
    catalog: SpecimenPreanalyticFixtureCatalog,
    expectation: SpecimenPreanalyticReplayExpectation | None = None,
    *,
    path: str = "examples/specimen-preanalytic-public-aggregate.json",
) -> SpecimenPreanalyticReplayReport:
    """Run the evaluator and compare it with explicit release floors."""

    expected = expectation or default_specimen_preanalytic_expectation(catalog)
    evaluation = evaluate_specimen_preanalytic_fixture(catalog)
    failures = _compare(expected, evaluation)
    body = {
        "path": path,
        "fixture_id": catalog.fixture_id,
        "state": evaluation.state,
        "failures": failures,
    }
    entry = SpecimenPreanalyticReplayEntry(
        path=path,
        fixture_id=catalog.fixture_id,
        state=evaluation.state,
        passed=not failures and evaluation.passed,
        failed_expectations=failures,
        content_address=content_hash(body),
    )
    report_body = {
        "expectation": expected,
        "entries": (entry,),
        "state": "accepted" if entry.passed else "review",
    }
    return SpecimenPreanalyticReplayReport(
        expected,
        (entry,),
        report_body["state"],
        content_hash(report_body),
    )


def replay_specimen_preanalytic_file(
    path: str | Path,
    expectation: SpecimenPreanalyticReplayExpectation | None = None,
) -> SpecimenPreanalyticReplayReport:
    catalog = SpecimenPreanalyticFixtureCatalog.from_file(path)
    return replay_specimen_preanalytic_fixture(catalog, expectation, path=str(path))


def _compare(
    expectation: SpecimenPreanalyticReplayExpectation,
    evaluation: SpecimenPreanalyticEvaluationReport,
) -> tuple[str, ...]:
    failures: list[str] = []
    if evaluation.fixture_id != expectation.fixture_id:
        failures.append("fixture_id")
    if evaluation.fixture_context_key != expectation.required_context_key:
        failures.append("context_key")
    if not evaluation.passed:
        failures.append("evaluation_state")
    if len(evaluation.receipts) < expectation.minimum_receipts:
        failures.append("receipt_floor")
    if len(evaluation.checks) < expectation.minimum_checks:
        failures.append("check_floor")
    if (
        sum(receipt.role == "positive" for receipt in evaluation.receipts)
        != expectation.positive_count
    ):
        failures.append("positive_count")
    if (
        sum(receipt.role == "control" for receipt in evaluation.receipts)
        != expectation.control_count
    ):
        failures.append("control_count")
    if set(evaluation.operation_ids) != {
        "preanalytic_quality",
        "assay_lineage",
        "identity_adjudication",
        "context_envelope",
    }:
        failures.append("operation_coverage")
    return tuple(failures)


__all__ = [
    "SpecimenPreanalyticReplayEntry",
    "SpecimenPreanalyticReplayExpectation",
    "SpecimenPreanalyticReplayReport",
    "default_specimen_preanalytic_expectation",
    "replay_specimen_preanalytic_file",
    "replay_specimen_preanalytic_fixture",
]
