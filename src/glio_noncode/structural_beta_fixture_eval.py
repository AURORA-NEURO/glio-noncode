"""Executable fixture evaluation for Domain 02 C05-C08.

Each record is executed through the existing scientific-beta detector rather
than through a second implementation.  The evaluator compares the observed
detector state, result counts, issue codes, and content address to the
declarations in the public aggregate fixture.  Published receipts contain
only bounded summaries and raw hashes; detector issue payloads are not copied
into the evaluation report.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable
from .structural_beta import (
    ChromothripsisPatternDetector,
    EnhancerHijackingCandidateDetector,
    ExtrachromosomalDnaCandidateDetector,
    FocalAmplificationBoundaryMapper,
    StructuralBetaState,
)
from .structural_beta_public_data import (
    StructuralBetaFixtureCatalog,
    StructuralBetaFixtureRecord,
    StructuralBetaFixtureState,
    StructuralBetaOperation,
)

_ACCEPTABLE_POSITIVE_STATES = {
    StructuralBetaState.SUPPORTED,
    StructuralBetaState.PARTIAL,
    StructuralBetaState.AMBIGUOUS,
}


@dataclass(frozen=True, slots=True)
class StructuralBetaExecution:
    """Sanitized output of one beta detector execution."""

    operation: StructuralBetaOperation
    observed_result_state: str
    issue_codes: tuple[str, ...]
    output_address: str
    counts: Mapping[str, int]
    output: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralBetaFixtureCheck:
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
class StructuralBetaOperationReceipt:
    """Stable record-level receipt for one C05-C08 operation."""

    record_id: str
    operation: StructuralBetaOperation
    expected_state: StructuralBetaFixtureState
    observed_state: StructuralBetaFixtureState
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
class StructuralBetaFixtureEvaluationReport:
    """Complete execution and assertion report for a beta fixture."""

    fixture_id: str
    context_key: str
    state: StructuralBetaFixtureState
    receipts: tuple[StructuralBetaOperationReceipt, ...]
    checks: tuple[StructuralBetaFixtureCheck, ...]
    positive_count: int
    control_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralBetaFixtureState.ACCEPTED and all(
            check.passed for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        result["receipt_count"] = len(self.receipts)
        result["positive_count"] = self.positive_count
        result["control_count"] = self.control_count
        return result


def evaluate_structural_beta_fixture(
    fixture: StructuralBetaFixtureCatalog | str,
) -> StructuralBetaFixtureEvaluationReport:
    """Execute every positive and control record through C05-C08 adapters."""

    catalog = (
        StructuralBetaFixtureCatalog.from_file(fixture)
        if isinstance(fixture, str)
        else fixture
    )
    receipts: list[StructuralBetaOperationReceipt] = []
    checks: list[StructuralBetaFixtureCheck] = []
    for record in catalog.positives + catalog.controls:
        execution = _execute(record)
        record_checks = _checks_for_record(record, execution)
        checks.extend(record_checks)
        receipts.append(
            StructuralBetaOperationReceipt(
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
        StructuralBetaFixtureState.ACCEPTED
        if all(check.passed for check in checks)
        else StructuralBetaFixtureState.REVIEW
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
    return StructuralBetaFixtureEvaluationReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        receipts=tuple(receipts),
        checks=tuple(checks),
        positive_count=len(catalog.positives),
        control_count=len(catalog.controls),
        content_address=content_hash(body),
    )


def _execute(record: StructuralBetaFixtureRecord) -> StructuralBetaExecution:
    payload = record.payload
    records = payload.get("records", ())
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        return _failed_execution(record, "records_not_array", "beta operation records must be an array")
    parameters = payload.get("parameters", {})
    if not isinstance(parameters, Mapping):
        return _failed_execution(record, "parameters_not_object", "beta operation parameters must be an object")
    try:
        if record.operation == StructuralBetaOperation.FOCAL_AMPLIFICATION:
            report = FocalAmplificationBoundaryMapper().map(
                records,
                context_key=record.context_key,
                **dict(parameters),
            )
        elif record.operation == StructuralBetaOperation.CHROMOTHRIPSIS:
            report = ChromothripsisPatternDetector().detect(
                records,
                context_key=record.context_key,
                **dict(parameters),
            )
        elif record.operation == StructuralBetaOperation.ECDNA:
            report = ExtrachromosomalDnaCandidateDetector().detect(
                records,
                context_key=record.context_key,
                **dict(parameters),
            )
        else:
            report = EnhancerHijackingCandidateDetector().detect(
                records,
                context_key=record.context_key,
                **dict(parameters),
            )
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        return _failed_execution(record, "validation_error", f"beta operation input failed validation: {exc}")
    candidates = tuple(getattr(report, "candidates", ()))
    issues = tuple(getattr(report, "issues", ()))
    safe_issues = tuple(_safe_issue(issue) for issue in issues)
    safe_candidates = tuple(_safe_candidate(candidate) for candidate in candidates)
    counts = {
        "input_records": len(records),
        "candidates": len(candidates),
        "issues": len(issues),
    }
    output = {
        "operation": record.operation.value,
        "result_state": report.state.value,
        "counts": counts,
        "candidates": safe_candidates,
        "issues": safe_issues,
        "warnings": tuple(str(item) for item in getattr(report, "warnings", ())),
    }
    return StructuralBetaExecution(
        operation=record.operation,
        observed_result_state=report.state.value,
        issue_codes=tuple(sorted(str(issue.code) for issue in issues)),
        output_address=str(report.content_address),
        counts=counts,
        output=output,
        detail=_detail(record.operation, report.state, len(candidates), len(issues)),
    )


def _checks_for_record(
    record: StructuralBetaFixtureRecord,
    execution: StructuralBetaExecution,
) -> tuple[StructuralBetaFixtureCheck, ...]:
    observed_state = _observed_fixture_state(record, execution)
    checks: list[StructuralBetaFixtureCheck] = [
        _check(
            record,
            "state",
            "state",
            record.expected_state.value,
            observed_state.value,
            "fixture-level positive or review state",
        ),
        _check(
            record,
            "result-state",
            "result_state",
            record.expected_result_state,
            execution.observed_result_state,
            "detector result state",
        ),
        _check(
            record,
            "output-address",
            "address",
            "sha256:",
            execution.output_address[:7],
            "detector output is content-addressed",
        ),
    ]
    for key, expected in sorted(record.expected_counts.items()):
        checks.append(
            _check(
                record,
                f"count-{key}",
                "count",
                int(expected),
                int(execution.counts.get(key, -1)),
                f"declared {key} count",
            )
        )
    for issue_code in record.required_issue_codes:
        checks.append(
            _check(
                record,
                f"issue-{issue_code}",
                "issue",
                issue_code,
                issue_code if issue_code in execution.issue_codes else None,
                "required issue remains visible",
            )
        )
    return tuple(checks)


def _observed_fixture_state(
    record: StructuralBetaFixtureRecord,
    execution: StructuralBetaExecution,
) -> StructuralBetaFixtureState:
    if record.expected_state == StructuralBetaFixtureState.REVIEW:
        return StructuralBetaFixtureState.REVIEW
    try:
        result_state = StructuralBetaState(execution.observed_result_state)
    except ValueError:
        return StructuralBetaFixtureState.REVIEW
    return (
        StructuralBetaFixtureState.ACCEPTED
        if result_state in _ACCEPTABLE_POSITIVE_STATES and not execution.issue_codes
        else StructuralBetaFixtureState.REVIEW
    )


def _failed_execution(
    record: StructuralBetaFixtureRecord,
    issue_code: str,
    detail: str,
) -> StructuralBetaExecution:
    output = {
        "operation": record.operation.value,
        "result_state": StructuralBetaState.INVALID.value,
        "counts": {"input_records": 0, "candidates": 0, "issues": 1},
        "candidates": (),
        "issues": ({"code": issue_code, "message": detail},),
        "warnings": (),
    }
    return StructuralBetaExecution(
        operation=record.operation,
        observed_result_state=StructuralBetaState.INVALID.value,
        issue_codes=(issue_code,),
        output_address=content_hash(output),
        counts=output["counts"],
        output=output,
        detail=detail,
    )


def _safe_issue(issue: Any) -> dict[str, Any]:
    return {
        "code": str(getattr(issue, "code", "unknown_issue")),
        "message": str(getattr(issue, "message", "")),
        "raw_hash": str(getattr(issue, "raw_hash", "")),
        "row_number": getattr(issue, "row_number", None),
        "source_id": str(getattr(issue, "source_id", "unspecified")),
        "severity": str(getattr(issue, "severity", "warning")),
    }


def _safe_candidate(candidate: Any) -> dict[str, Any]:
    if hasattr(candidate, "to_dict"):
        result = dict(candidate.to_dict())
        result.pop("raw_record", None)
        return result
    return {"candidate_id": str(getattr(candidate, "candidate_id", "unknown"))}


def _check(
    record: StructuralBetaFixtureRecord,
    suffix: str,
    check_kind: str,
    expected: Any,
    observed: Any,
    detail: str,
) -> StructuralBetaFixtureCheck:
    return StructuralBetaFixtureCheck(
        check_id=f"{record.record_id}:{suffix}",
        record_id=record.record_id,
        check_kind=check_kind,
        passed=expected == observed,
        expected=expected,
        observed=observed,
        detail=detail,
    )


def _detail(operation: StructuralBetaOperation, state: Any, candidates: int, issues: int) -> str:
    return (
        f"{operation.value} returned {state.value} with {candidates} candidate(s) "
        f"and {issues} issue(s)"
    )


__all__ = [
    "StructuralBetaExecution",
    "StructuralBetaFixtureCheck",
    "StructuralBetaFixtureEvaluationReport",
    "StructuralBetaOperationReceipt",
    "evaluate_structural_beta_fixture",
]
