"""Executable fixture evaluation for Domain 02 C13-C16."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import (
    BreakpointUncertaintyPropagator,
    CompoundHaplotypeEvaluator,
    FrontierState,
    StructuralVariantEvidenceExporter,
    TandemRepeatInterpreter,
)
from .serialization import content_hash, jsonable
from .structural_frontier_public_data import (
    StructuralFrontierFixtureCatalog,
    StructuralFrontierFixtureRecord,
    StructuralFrontierFixtureState,
    StructuralFrontierOperation,
)


@dataclass(frozen=True, slots=True)
class StructuralFrontierExecution:
    """Sanitized result of one adapter invocation."""

    operation: StructuralFrontierOperation
    observed_result_state: str
    issue_codes: tuple[str, ...]
    output_address: str
    counts: Mapping[str, int]
    output: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierFixtureCheck:
    """One explicit expected-versus-observed assertion."""

    check_id: str
    record_id: str
    operation: StructuralFrontierOperation
    check_kind: str
    expected: Any
    observed: Any
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierOperationReceipt:
    """Review-safe receipt for one positive or control record."""

    record_id: str
    operation: StructuralFrontierOperation
    expected_state: StructuralFrontierFixtureState
    observed_state: StructuralFrontierFixtureState
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
class StructuralFrontierFixtureEvaluationReport:
    """Full deterministic evaluation report for the aggregate fixture."""

    fixture_id: str
    context_key: str
    state: StructuralFrontierFixtureState
    receipts: tuple[StructuralFrontierOperationReceipt, ...]
    checks: tuple[StructuralFrontierFixtureCheck, ...]
    positive_count: int
    control_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralFrontierFixtureState.ACCEPTED and all(
            check.passed for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "check_count": len(self.checks),
            "receipt_count": len(self.receipts),
        }


def evaluate_structural_frontier_fixture(
    fixture: StructuralFrontierFixtureCatalog | str,
) -> StructuralFrontierFixtureEvaluationReport:
    """Execute every positive and review control through C13-C16 adapters."""

    catalog = (
        StructuralFrontierFixtureCatalog.from_file(fixture)
        if isinstance(fixture, str)
        else fixture
    )
    receipts: list[StructuralFrontierOperationReceipt] = []
    checks: list[StructuralFrontierFixtureCheck] = []
    for record in catalog.positives + catalog.controls:
        execution = _execute(record)
        record_checks = _checks_for_record(record, execution)
        checks.extend(record_checks)
        receipts.append(
            StructuralFrontierOperationReceipt(
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
        StructuralFrontierFixtureState.ACCEPTED
        if all(check.passed for check in checks)
        else StructuralFrontierFixtureState.REVIEW
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
    return StructuralFrontierFixtureEvaluationReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        receipts=tuple(receipts),
        checks=tuple(checks),
        positive_count=len(catalog.positives),
        control_count=len(catalog.controls),
        content_address=content_hash(body),
    )


def _execute(record: StructuralFrontierFixtureRecord) -> StructuralFrontierExecution:
    payload = record.payload
    parameters = payload.get("parameters", {})
    if not isinstance(parameters, Mapping):
        return _failed_execution(record, "parameters_not_object", "operation parameters must be an object")
    try:
        if record.operation == StructuralFrontierOperation.TANDEM_REPEAT:
            report = TandemRepeatInterpreter().interpret(
                _records(payload.get("records", ())),
                context_key=record.context_key,
                source_id=record.source_id,
                **dict(parameters),
            )
            counts = {
                "observations": len(report.observations),
                "expanded": len(report.expanded_ids),
                "contracted": len(report.contracted_ids),
                "review": len(report.review_ids),
            }
        elif record.operation == StructuralFrontierOperation.COMPOUND_HAPLOTYPE:
            report = CompoundHaplotypeEvaluator().evaluate(
                _records(payload.get("records", ())),
                context_key=record.context_key,
                **dict(parameters),
            )
            counts = {
                "evaluations": len(report.evaluations),
                "compatible": len(report.compatible_ids),
                "review": len(report.review_ids),
            }
        elif record.operation == StructuralFrontierOperation.BREAKPOINT_UNCERTAINTY:
            report = BreakpointUncertaintyPropagator().propagate(
                _records(payload.get("records", ())),
                context_key=record.context_key,
                source_id=record.source_id,
                **dict(parameters),
            )
            counts = {
                "intervals": len(report.intervals),
                "high_confidence": len(report.high_confidence_ids),
                "review": len(report.review_ids),
            }
        else:
            report = StructuralVariantEvidenceExporter().export(
                _records(payload.get("evidence", payload.get("records", ()))),
                bundle_id=str(payload.get("bundle_id", f"{record.record_id}-bundle")),
                context_key=record.context_key,
                required_fields=tuple(
                    str(field)
                    for field in parameters.get(
                        "required_fields", ("variant_id", "evidence_type", "source_id")
                    )
                ),
            )
            counts = {
                "evidence": report.evidence_count,
                "sources": len(report.source_ids),
                "published": int(report.state == FrontierState.PUBLISHED),
            }
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        return _failed_execution(record, "validation_error", f"operation input failed validation: {exc}")
    issues = _report_issue_codes(record.operation, report)
    result_state = _report_state(record.operation, report)
    output = {
        "operation": record.operation.value,
        "result_state": result_state.value,
        "counts": counts,
        "issue_codes": issues,
    }
    return StructuralFrontierExecution(
        operation=record.operation,
        observed_result_state=result_state.value,
        issue_codes=issues,
        output_address=str(report.content_address),
        counts=counts,
        output=output,
        detail=_detail(record.operation, result_state, counts),
    )


def _records(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError("operation records must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValidationError("operation records must contain objects")
    return tuple(value)


def _checks_for_record(
    record: StructuralFrontierFixtureRecord,
    execution: StructuralFrontierExecution,
) -> tuple[StructuralFrontierFixtureCheck, ...]:
    observed_state = _observed_fixture_state(record, execution)
    checks: list[StructuralFrontierFixtureCheck] = [
        _check(record, "state", "state", record.expected_state.value, observed_state.value, "fixture state"),
        _check(record, "result-state", "result_state", record.expected_result_state, execution.observed_result_state, "adapter result state"),
        _check(record, "output-address", "address", "sha256:", execution.output_address[:7], "adapter output is addressed"),
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
    record: StructuralFrontierFixtureRecord,
    execution: StructuralFrontierExecution,
) -> StructuralFrontierFixtureState:
    if record.expected_state == StructuralFrontierFixtureState.REVIEW:
        return StructuralFrontierFixtureState.REVIEW
    try:
        result_state = FrontierState(execution.observed_result_state)
    except ValueError:
        return StructuralFrontierFixtureState.REVIEW
    return (
        StructuralFrontierFixtureState.ACCEPTED
        if result_state in {FrontierState.ACCEPTED, FrontierState.PUBLISHED}
        and not execution.issue_codes
        else StructuralFrontierFixtureState.REVIEW
    )


def _failed_execution(
    record: StructuralFrontierFixtureRecord,
    issue_code: str,
    detail: str,
) -> StructuralFrontierExecution:
    counts = {
        "observations": 0,
        "expanded": 0,
        "contracted": 0,
        "evaluations": 0,
        "compatible": 0,
        "intervals": 0,
        "high_confidence": 0,
        "evidence": 0,
        "sources": 0,
        "published": 0,
        "review": 0,
    }
    output = {
        "record_id": record.record_id,
        "operation": record.operation.value,
        "result_state": "invalid",
        "counts": counts,
        "issue_codes": (issue_code,),
    }
    return StructuralFrontierExecution(
        operation=record.operation,
        observed_result_state="invalid",
        issue_codes=(issue_code,),
        output_address=content_hash(output),
        counts=counts,
        output=output,
        detail=detail,
    )


def _report_issue_codes(operation: StructuralFrontierOperation, report: Any) -> tuple[str, ...]:
    if operation == StructuralFrontierOperation.TANDEM_REPEAT:
        observations = report.observations
    elif operation == StructuralFrontierOperation.COMPOUND_HAPLOTYPE:
        observations = report.evaluations
    elif operation == StructuralFrontierOperation.BREAKPOINT_UNCERTAINTY:
        observations = report.intervals
    else:
        observations = ()
    return tuple(
        sorted(
            {
                str(getattr(issue, "code", "unknown_issue"))
                for observation in observations
                for issue in observation.issues
            }
        )
    )


def _report_state(operation: StructuralFrontierOperation, report: Any) -> FrontierState:
    if operation == StructuralFrontierOperation.STRUCTURAL_EVIDENCE_EXPORT:
        return report.state
    review_ids = report.review_ids
    return FrontierState.REVIEW if review_ids else FrontierState.ACCEPTED


def _check(
    record: StructuralFrontierFixtureRecord,
    suffix: str,
    check_kind: str,
    expected: Any,
    observed: Any,
    detail: str,
) -> StructuralFrontierFixtureCheck:
    return StructuralFrontierFixtureCheck(
        check_id=f"{record.record_id}:{suffix}",
        record_id=record.record_id,
        operation=record.operation,
        check_kind=check_kind,
        expected=expected,
        observed=observed,
        passed=expected == observed or (expected == "sha256:" and str(observed).startswith("sha256:")),
        detail=detail,
    )


def _detail(
    operation: StructuralFrontierOperation,
    state: FrontierState,
    counts: Mapping[str, int],
) -> str:
    primary = {
        StructuralFrontierOperation.TANDEM_REPEAT: "observations",
        StructuralFrontierOperation.COMPOUND_HAPLOTYPE: "evaluations",
        StructuralFrontierOperation.BREAKPOINT_UNCERTAINTY: "intervals",
        StructuralFrontierOperation.STRUCTURAL_EVIDENCE_EXPORT: "evidence",
    }[operation]
    return f"{operation.value} returned {counts.get(primary, 0)} {primary} in {state.value} state"


__all__ = [
    "StructuralFrontierExecution",
    "StructuralFrontierFixtureCheck",
    "StructuralFrontierFixtureEvaluationReport",
    "StructuralFrontierOperationReceipt",
    "evaluate_structural_frontier_fixture",
]
