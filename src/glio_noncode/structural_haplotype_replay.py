"""Replay and drift checks for the Domain 02 C09-C12 fixture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable
from .structural_haplotype_fixture_eval import evaluate_structural_haplotype_fixture
from .structural_haplotype_public_data import (
    STRUCTURAL_HAPLOTYPE_CONTROL_FLOOR,
    STRUCTURAL_HAPLOTYPE_OPERATION_FLOOR,
    StructuralHaplotypeFixtureCatalog,
    audit_structural_haplotype_fixture,
)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeReplayExpectation:
    """Minimum identity and evidence floor for one replay invocation."""

    fixture_id: str
    context_key: str
    source_ids: tuple[str, ...]
    minimum_checks: int = 40
    minimum_positive_records: int = STRUCTURAL_HAPLOTYPE_OPERATION_FLOOR
    minimum_control_records: int = STRUCTURAL_HAPLOTYPE_CONTROL_FLOOR


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeReplayCase:
    """One replayed fixture and its identity comparison result."""

    path: str
    fixture_id: str
    context_key: str
    content_address: str
    evaluation_address: str
    passed: bool
    issue_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeReplayReport:
    """Aggregate replay result with duplicate and drift detection."""

    cases: tuple[StructuralHaplotypeReplayCase, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return not self.issue_codes and all(case.passed for case in self.cases)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed, "case_count": len(self.cases)}


def replay_structural_haplotype_fixtures(
    paths: tuple[str, ...] | list[str],
    *,
    expectation: StructuralHaplotypeReplayExpectation | None = None,
    required_context_key: str | None = None,
) -> StructuralHaplotypeReplayReport:
    """Replay C09-C12 fixtures and reject identity or context drift."""

    if not paths:
        raise ValidationError("at least one structural haplotype fixture path is required")
    cases: list[StructuralHaplotypeReplayCase] = []
    issues: set[str] = set()
    catalogs: list[StructuralHaplotypeFixtureCatalog] = []
    for raw_path in paths:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(raw_path)
        catalogs.append(catalog)
        audit = audit_structural_haplotype_fixture(catalog)
        evaluation = evaluate_structural_haplotype_fixture(catalog)
        case_issues = set(audit.issue_codes)
        if not evaluation.passed:
            case_issues.add("evaluation_failed")
        if required_context_key is not None and catalog.context_key != required_context_key:
            case_issues.add("context_mismatch")
        if expectation is not None:
            _apply_expectation(catalog, evaluation, expectation, case_issues)
        cases.append(
            StructuralHaplotypeReplayCase(
                path=str(Path(raw_path)),
                fixture_id=catalog.fixture_id,
                context_key=catalog.context_key,
                content_address=catalog.content_address,
                evaluation_address=evaluation.content_address,
                passed=not case_issues,
                issue_codes=tuple(sorted(case_issues)),
            )
        )
    fixture_ids = [case.fixture_id for case in cases]
    addresses = [case.content_address for case in cases]
    if len(fixture_ids) != len(set(fixture_ids)):
        issues.add("duplicate_fixture_identity")
    if len(addresses) != len(set(addresses)):
        issues.add("duplicate_fixture_address")
    if any(catalog.context_key != catalogs[0].context_key for catalog in catalogs[1:]):
        issues.add("cross_fixture_context_drift")
    body = {"cases": cases, "issues": tuple(sorted(issues))}
    return StructuralHaplotypeReplayReport(
        cases=tuple(cases),
        issue_codes=tuple(sorted(issues)),
        content_address=content_hash(body),
    )


def _apply_expectation(
    catalog: StructuralHaplotypeFixtureCatalog,
    evaluation: Any,
    expectation: StructuralHaplotypeReplayExpectation,
    issues: set[str],
) -> None:
    if catalog.fixture_id != expectation.fixture_id:
        issues.add("fixture_id_mismatch")
    if catalog.context_key != expectation.context_key:
        issues.add("expected_context_mismatch")
    if catalog.source_ids != tuple(sorted(expectation.source_ids)):
        issues.add("source_set_mismatch")
    if len(evaluation.checks) < expectation.minimum_checks:
        issues.add("check_floor")
    if len(catalog.positives) < expectation.minimum_positive_records:
        issues.add("positive_floor")
    if len(catalog.controls) < expectation.minimum_control_records:
        issues.add("control_floor")


__all__ = [
    "StructuralHaplotypeReplayCase",
    "StructuralHaplotypeReplayExpectation",
    "StructuralHaplotypeReplayReport",
    "replay_structural_haplotype_fixtures",
]
