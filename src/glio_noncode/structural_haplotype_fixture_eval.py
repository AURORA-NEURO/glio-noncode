"""Executable fixture evaluation for Domain 02 C09-C12.

Each record is executed through the existing structural haplotype adapters.
The evaluator compares result states, operation counts, required issue codes,
and content addresses to the declarations in the public aggregate fixture.
Published receipts retain only bounded summaries and hashes; raw operation
payloads and issue records are never copied into the evaluation report.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable
from .structural_haplotype import (
    AlleleAwareSvRepresenter,
    PangenomeGraphProjector,
    PhasedHaplotypeAssembler,
    RepeatMobileElementAnnotator,
    StructuralAlphaState,
)
from .structural_haplotype_public_data import (
    StructuralHaplotypeFixtureCatalog,
    StructuralHaplotypeFixtureRecord,
    StructuralHaplotypeFixtureState,
    StructuralHaplotypeOperation,
)

_ACCEPTABLE_POSITIVE_STATES = {
    StructuralAlphaState.SUPPORTED,
    StructuralAlphaState.PARTIAL,
    StructuralAlphaState.AMBIGUOUS,
}


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeExecution:
    """Sanitized output of one structural haplotype operation."""

    operation: StructuralHaplotypeOperation
    observed_result_state: str
    issue_codes: tuple[str, ...]
    output_address: str
    counts: Mapping[str, int]
    output: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeFixtureCheck:
    """One explicit assertion over a positive or review record."""

    check_id: str
    record_id: str | None
    check_kind: str
    passed: bool
    expected: Any
    observed: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeOperationReceipt:
    """Stable record-level receipt for one C09-C12 operation."""

    record_id: str
    operation: StructuralHaplotypeOperation
    expected_state: StructuralHaplotypeFixtureState
    observed_state: StructuralHaplotypeFixtureState
    expected_result_state: str
    observed_result_state: str
    issue_codes: tuple[str, ...]
    output_address: str
    counts: Mapping[str, int]
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeFixtureEvaluationReport:
    """Complete execution and assertion report for a C09-C12 fixture."""

    fixture_id: str
    context_key: str
    state: StructuralHaplotypeFixtureState
    receipts: tuple[StructuralHaplotypeOperationReceipt, ...]
    checks: tuple[StructuralHaplotypeFixtureCheck, ...]
    positive_count: int
    control_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralHaplotypeFixtureState.ACCEPTED and all(
            check.passed for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "check_count": len(self.checks),
            "receipt_count": len(self.receipts),
        }


def evaluate_structural_haplotype_fixture(
    fixture: StructuralHaplotypeFixtureCatalog | str,
) -> StructuralHaplotypeFixtureEvaluationReport:
    """Execute every positive and control record through C09-C12 adapters."""

    catalog = (
        StructuralHaplotypeFixtureCatalog.from_file(fixture)
        if isinstance(fixture, str)
        else fixture
    )
    receipts: list[StructuralHaplotypeOperationReceipt] = []
    checks: list[StructuralHaplotypeFixtureCheck] = []
    for record in catalog.positives + catalog.controls:
        execution = _execute(record)
        record_checks = _checks_for_record(record, execution)
        checks.extend(record_checks)
        receipts.append(
            StructuralHaplotypeOperationReceipt(
                record_id=record.record_id,
                operation=record.operation,
                expected_state=record.expected_state,
                observed_state=_observed_fixture_state(record, execution),
                expected_result_state=record.expected_result_state,
                observed_result_state=execution.observed_result_state,
                issue_codes=execution.issue_codes,
                output_address=execution.output_address,
                counts=execution.counts,
                passed=all(check.passed for check in record_checks),
                detail=execution.detail,
            )
        )
    state = (
        StructuralHaplotypeFixtureState.ACCEPTED
        if all(check.passed for check in checks)
        else StructuralHaplotypeFixtureState.REVIEW
    )
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "state": state,
        "receipts": receipts,
        "checks": checks,
        "positive_count": len(catalog.positives),
        "control_count": len(catalog.controls),
    }
    return StructuralHaplotypeFixtureEvaluationReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        receipts=tuple(receipts),
        checks=tuple(checks),
        positive_count=len(catalog.positives),
        control_count=len(catalog.controls),
        content_address=content_hash(body),
    )


def _execute(record: StructuralHaplotypeFixtureRecord) -> StructuralHaplotypeExecution:
    payload = record.payload
    parameters = payload.get("parameters", {})
    if not isinstance(parameters, Mapping):
        return _failed_execution(record, "parameters_not_object", "operation parameters must be an object")
    try:
        if record.operation == StructuralHaplotypeOperation.PHASED_HAPLOTYPE:
            report = PhasedHaplotypeAssembler().assemble(
                _records(payload.get("records", ())),
                context_key=record.context_key,
                **dict(parameters),
            )
            counts = {
                "haplotypes": len(report.haplotypes),
                "unphased": len(report.unphased_observations),
                "issues": len(report.issues),
            }
        elif record.operation == StructuralHaplotypeOperation.ALLELE_AWARE_SV:
            report = AlleleAwareSvRepresenter().represent(
                _records(payload.get("records", ())),
                context_key=record.context_key,
            )
            counts = {"events": len(report.events), "issues": len(report.issues)}
        elif record.operation == StructuralHaplotypeOperation.PANGENOME_PROJECTION:
            report = PangenomeGraphProjector().project(
                _records(payload.get("queries", ())),
                _records(payload.get("nodes", ())),
                context_key=record.context_key,
                **dict(parameters),
            )
            counts = {
                "matches": len(report.matches),
                "unmapped": len(report.unmapped_query_ids),
                "issues": len(report.issues),
            }
        else:
            report = RepeatMobileElementAnnotator().annotate(
                _records(payload.get("queries", ())),
                _records(payload.get("annotations", ())),
                context_key=record.context_key,
                **dict(parameters),
            )
            counts = {
                "hits": len(report.hits),
                "unannotated": len(report.unannotated_query_ids),
                "issues": len(report.issues),
            }
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        return _failed_execution(record, "validation_error", f"operation input failed validation: {exc}")
    issues = tuple(getattr(issue, "code", "unknown_issue") for issue in report.issues)
    output = {
        "operation": record.operation.value,
        "result_state": report.state.value,
        "counts": counts,
        "issue_codes": tuple(sorted(str(code) for code in issues)),
    }
    return StructuralHaplotypeExecution(
        operation=record.operation,
        observed_result_state=report.state.value,
        issue_codes=tuple(sorted(str(code) for code in issues)),
        output_address=str(report.content_address),
        counts=counts,
        output=output,
        detail=_detail(record.operation, report.state, counts),
    )


def _records(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError("operation records must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValidationError("operation records must contain objects")
    return tuple(value)


def _checks_for_record(
    record: StructuralHaplotypeFixtureRecord,
    execution: StructuralHaplotypeExecution,
) -> tuple[StructuralHaplotypeFixtureCheck, ...]:
    observed_state = _observed_fixture_state(record, execution)
    checks: list[StructuralHaplotypeFixtureCheck] = [
        _check(record, "state", "state", record.expected_state.value, observed_state.value, "fixture state"),
        _check(record, "result-state", "result_state", record.expected_result_state, execution.observed_result_state, "detector result state"),
        _check(record, "output-address", "address", "sha256:", execution.output_address[:7], "detector output is addressed"),
    ]
    for key, expected in sorted(record.expected_counts.items()):
        checks.append(
            _check(record, f"count-{key}", "count", int(expected), int(execution.counts.get(key, -1)), f"declared {key} count")
        )
    for issue_code in record.required_issue_codes:
        checks.append(
            _check(record, f"issue-{issue_code}", "issue", issue_code, issue_code if issue_code in execution.issue_codes else None, "required issue remains visible")
        )
    return tuple(checks)


def _observed_fixture_state(
    record: StructuralHaplotypeFixtureRecord,
    execution: StructuralHaplotypeExecution,
) -> StructuralHaplotypeFixtureState:
    if record.expected_state == StructuralHaplotypeFixtureState.REVIEW:
        return StructuralHaplotypeFixtureState.REVIEW
    try:
        result_state = StructuralAlphaState(execution.observed_result_state)
    except ValueError:
        return StructuralHaplotypeFixtureState.REVIEW
    return (
        StructuralHaplotypeFixtureState.ACCEPTED
        if result_state in _ACCEPTABLE_POSITIVE_STATES and not execution.issue_codes
        else StructuralHaplotypeFixtureState.REVIEW
    )


def _failed_execution(
    record: StructuralHaplotypeFixtureRecord,
    issue_code: str,
    detail: str,
) -> StructuralHaplotypeExecution:
    counts = {"issues": 1}
    output = {
        "operation": record.operation.value,
        "result_state": StructuralAlphaState.INVALID.value,
        "counts": counts,
        "issue_codes": (issue_code,),
    }
    return StructuralHaplotypeExecution(
        operation=record.operation,
        observed_result_state=StructuralAlphaState.INVALID.value,
        issue_codes=(issue_code,),
        output_address=content_hash(output),
        counts=counts,
        output=output,
        detail=detail,
    )


def _check(
    record: StructuralHaplotypeFixtureRecord,
    suffix: str,
    check_kind: str,
    expected: Any,
    observed: Any,
    detail: str,
) -> StructuralHaplotypeFixtureCheck:
    return StructuralHaplotypeFixtureCheck(
        check_id=f"{record.record_id}:{suffix}",
        record_id=record.record_id,
        check_kind=check_kind,
        passed=expected == observed,
        expected=expected,
        observed=observed,
        detail=detail,
    )


def _detail(operation: StructuralHaplotypeOperation, state: Any, counts: Mapping[str, int]) -> str:
    summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    return f"{operation.value} returned {state.value} ({summary})"


__all__ = [
    "StructuralHaplotypeExecution",
    "StructuralHaplotypeFixtureCheck",
    "StructuralHaplotypeFixtureEvaluationReport",
    "StructuralHaplotypeOperationReceipt",
    "evaluate_structural_haplotype_fixture",
]
