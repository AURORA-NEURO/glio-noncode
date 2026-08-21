"""Deterministic execution receipts for Domain 03 C01-C04."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable
from .specimen_context import (
    ContaminationSwapDetector,
    MatchedNormalResolver,
    PurityPloidyImporter,
    SampleFingerprint,
    SampleIntegrityState,
    SpecimenEvidenceState,
    SpecimenOntologyMapper,
)
from .specimen_frontier_public_data import (
    SpecimenFrontierFixtureCatalog,
    SpecimenFrontierFixtureRecord,
    SpecimenFrontierFixtureState,
    SpecimenFrontierOperation,
)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierExecution:
    """Sanitized result of one specimen adapter invocation."""

    operation: SpecimenFrontierOperation
    observed_result_state: str
    issue_codes: tuple[str, ...]
    output_address: str
    counts: Mapping[str, int]
    output: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierFixtureCheck:
    """One explicit expected-versus-observed assertion."""

    check_id: str
    record_id: str
    operation: SpecimenFrontierOperation
    check_kind: str
    expected: Any
    observed: Any
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierOperationReceipt:
    """Review-safe receipt for one positive or control record."""

    record_id: str
    operation: SpecimenFrontierOperation
    expected_state: SpecimenFrontierFixtureState
    observed_state: SpecimenFrontierFixtureState
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
class SpecimenFrontierFixtureEvaluationReport:
    """Full deterministic evaluation report for the aggregate fixture."""

    fixture_id: str
    context_key: str
    receipts: tuple[SpecimenFrontierOperationReceipt, ...]
    checks: tuple[SpecimenFrontierFixtureCheck, ...]
    state: SpecimenFrontierFixtureState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == SpecimenFrontierFixtureState.ACCEPTED and all(
            check.passed for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "receipt_count": len(self.receipts),
            "check_count": len(self.checks),
        }


def evaluate_specimen_frontier_fixture(
    fixture: SpecimenFrontierFixtureCatalog | str,
) -> SpecimenFrontierFixtureEvaluationReport:
    """Execute every positive and review control through C01-C04 adapters."""

    catalog = (
        SpecimenFrontierFixtureCatalog.from_file(fixture) if isinstance(fixture, str) else fixture
    )
    receipts: list[SpecimenFrontierOperationReceipt] = []
    checks: list[SpecimenFrontierFixtureCheck] = []
    for record in catalog.positives + catalog.controls:
        execution = _execute(record)
        record_checks = _checks_for_record(record, execution)
        checks.extend(record_checks)
        receipts.append(
            SpecimenFrontierOperationReceipt(
                record_id=record.record_id,
                operation=record.operation,
                expected_state=record.expected_state,
                observed_state=_observed_fixture_state(execution),
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
        SpecimenFrontierFixtureState.ACCEPTED
        if all(check.passed for check in checks)
        else SpecimenFrontierFixtureState.REVIEW
    )
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "receipts": receipts,
        "checks": checks,
        "state": state,
    }
    return SpecimenFrontierFixtureEvaluationReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        receipts=tuple(receipts),
        checks=tuple(checks),
        state=state,
        content_address=content_hash(body),
    )


def _execute(record: SpecimenFrontierFixtureRecord) -> SpecimenFrontierExecution:
    """Route one fixture record to exactly one typed adapter."""

    payload = record.payload
    parameters = record.parameters
    try:
        if record.operation == SpecimenFrontierOperation.ONTOLOGY_MAPPING:
            report = SpecimenOntologyMapper().parse_rows(
                payload.get("records", ()),
                source_id=record.source_id,
            )
            issue_codes = _ontology_issue_codes(report)
            if report.issues:
                result_state = "invalid"
            elif any(
                mapping.state == SpecimenEvidenceState.AMBIGUOUS for mapping in report.mappings
            ):
                result_state = "ambiguous"
            elif any(mapping.state == SpecimenEvidenceState.PARTIAL for mapping in report.mappings):
                result_state = "partial"
            else:
                result_state = "supported"
            counts = {
                "observations": len(report.observations),
                "mappings": len(report.mappings),
                "ambiguous": sum(
                    mapping.state == SpecimenEvidenceState.AMBIGUOUS for mapping in report.mappings
                ),
                "partial": sum(
                    mapping.state == SpecimenEvidenceState.PARTIAL for mapping in report.mappings
                ),
                "issues": len(report.issues),
            }
            output = {
                "record_id": record.record_id,
                "operation": record.operation.value,
                "result_state": result_state,
                "issue_codes": issue_codes,
                "counts": counts,
                "mapping_addresses": tuple(mapping.content_address for mapping in report.mappings),
            }
            return _execution(record, result_state, issue_codes, counts, output, "ontology mapping")

        if record.operation == SpecimenFrontierOperation.MATCHED_NORMAL:
            parsed = SpecimenOntologyMapper().parse_rows(
                payload.get("records", ()),
                source_id=record.source_id,
            )
            report = MatchedNormalResolver().resolve(parsed.observations)
            issue_codes = _matched_normal_issue_codes(parsed, report)
            if parsed.issues:
                result_state = "invalid"
            elif any(pair.state == SpecimenEvidenceState.AMBIGUOUS for pair in report.pairs):
                result_state = "ambiguous"
            elif any(pair.state == SpecimenEvidenceState.ABSTAINED for pair in report.pairs):
                result_state = "abstained"
            else:
                result_state = "supported"
            counts = {
                "observations": len(parsed.observations),
                "tumors": len(report.pairs),
                "supported": sum(
                    pair.state == SpecimenEvidenceState.SUPPORTED for pair in report.pairs
                ),
                "ambiguous": sum(
                    pair.state == SpecimenEvidenceState.AMBIGUOUS for pair in report.pairs
                ),
                "abstained": sum(
                    pair.state == SpecimenEvidenceState.ABSTAINED for pair in report.pairs
                ),
                "issues": len(parsed.issues),
            }
            output = {
                "record_id": record.record_id,
                "operation": record.operation.value,
                "result_state": result_state,
                "issue_codes": issue_codes,
                "counts": counts,
                "pair_addresses": tuple(pair.content_address for pair in report.pairs),
            }
            return _execution(
                record, result_state, issue_codes, counts, output, "matched-normal resolution"
            )

        if record.operation == SpecimenFrontierOperation.PURITY_PLOIDY:
            report = PurityPloidyImporter().parse_text(
                str(payload.get("text", "")),
                source_id=record.source_id,
                input_format=parameters.get("input_format"),
            )
            issue_codes = tuple(sorted({issue.code for issue in report.issues}))
            result_state = "accepted" if report.records and not report.issues else "review"
            counts = {
                "records": len(report.records),
                "issues": len(report.issues),
                "percent_normalized": sum(float(record.purity) <= 1.0 for record in report.records),
            }
            output = {
                "record_id": record.record_id,
                "operation": record.operation.value,
                "result_state": result_state,
                "issue_codes": issue_codes,
                "counts": counts,
                "record_addresses": tuple(record.raw_hash for record in report.records),
                "input_hash": report.input_hash,
            }
            return _execution(
                record, result_state, issue_codes, counts, output, "purity/ploidy import"
            )

        if record.operation == SpecimenFrontierOperation.SAMPLE_INTEGRITY:
            fingerprints = tuple(
                SampleFingerprint(
                    sample_id=str(item["sample_id"]),
                    declared_subject_id=(
                        str(item.get("declared_subject_id", item.get("declared_subject_key")))
                        if item.get("declared_subject_id", item.get("declared_subject_key"))
                        is not None
                        else None
                    ),
                    observed_subject_id=(
                        str(item.get("observed_subject_id", item.get("observed_subject_key")))
                        if item.get("observed_subject_id", item.get("observed_subject_key"))
                        is not None
                        else None
                    ),
                    contamination_fraction=item.get("contamination_fraction"),
                    discordance_rate=item.get("discordance_rate"),
                    marker_count=item.get("marker_count"),
                    source_id=record.source_id,
                    raw_hash=content_hash(item),
                )
                for item in payload.get("fingerprints", ())
            )
            detector = ContaminationSwapDetector(
                contamination_watch=float(parameters.get("contamination_watch", 0.02)),
                contamination_flag=float(parameters.get("contamination_flag", 0.05)),
                discordance_watch=float(parameters.get("discordance_watch", 0.02)),
            )
            assessments = detector.assess(fingerprints)
            issue_codes = _integrity_issue_codes(assessments)
            states = {assessment.state for assessment in assessments}
            if SampleIntegrityState.FLAGGED in states:
                result_state = SampleIntegrityState.FLAGGED.value
            elif SampleIntegrityState.WATCH in states:
                result_state = SampleIntegrityState.WATCH.value
            elif SampleIntegrityState.ABSTAINED in states:
                result_state = SampleIntegrityState.ABSTAINED.value
            else:
                result_state = SampleIntegrityState.CLEAR.value
            counts = {
                "fingerprints": len(fingerprints),
                "clear": sum(
                    assessment.state == SampleIntegrityState.CLEAR for assessment in assessments
                ),
                "watch": sum(
                    assessment.state == SampleIntegrityState.WATCH for assessment in assessments
                ),
                "flagged": sum(
                    assessment.state == SampleIntegrityState.FLAGGED for assessment in assessments
                ),
                "abstained": sum(
                    assessment.state == SampleIntegrityState.ABSTAINED for assessment in assessments
                ),
            }
            output = {
                "record_id": record.record_id,
                "operation": record.operation.value,
                "result_state": result_state,
                "issue_codes": issue_codes,
                "counts": counts,
                "assessment_addresses": tuple(
                    assessment.content_address for assessment in assessments
                ),
            }
            return _execution(
                record, result_state, issue_codes, counts, output, "sample integrity assessment"
            )

        raise ValidationError(f"unsupported specimen frontier operation: {record.operation}")
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        counts = {
            "observations": 0,
            "mappings": 0,
            "ambiguous": 0,
            "partial": 0,
            "tumors": 0,
            "supported": 0,
            "abstained": 0,
            "records": 0,
            "issues": 0,
            "percent_normalized": 0,
            "fingerprints": 0,
            "clear": 0,
            "watch": 0,
            "flagged": 0,
        }
        output = {
            "record_id": record.record_id,
            "operation": record.operation.value,
            "result_state": "invalid",
            "issue_codes": ("validation_error",),
            "counts": counts,
        }
        return _execution(
            record,
            "invalid",
            ("validation_error",),
            counts,
            output,
            f"operation input failed validation: {exc}",
        )


def _execution(
    record: SpecimenFrontierFixtureRecord,
    result_state: str,
    issue_codes: tuple[str, ...],
    counts: Mapping[str, int],
    output: Mapping[str, Any],
    detail: str,
) -> SpecimenFrontierExecution:
    sanitized = {
        "record_id": record.record_id,
        "operation": record.operation.value,
        "result_state": result_state,
        "issue_codes": tuple(sorted(issue_codes)),
        "counts": dict(sorted(counts.items())),
    }
    return SpecimenFrontierExecution(
        operation=record.operation,
        observed_result_state=result_state,
        issue_codes=tuple(sorted(issue_codes)),
        output_address=content_hash(sanitized),
        counts=counts,
        output=sanitized,
        detail=detail,
    )


def _observed_fixture_state(
    execution: SpecimenFrontierExecution,
) -> SpecimenFrontierFixtureState:
    accepted_states = {
        "supported",
        "accepted",
        SampleIntegrityState.CLEAR.value,
    }
    if execution.observed_result_state in accepted_states and not execution.issue_codes:
        return SpecimenFrontierFixtureState.ACCEPTED
    return SpecimenFrontierFixtureState.REVIEW


def _checks_for_record(
    record: SpecimenFrontierFixtureRecord,
    execution: SpecimenFrontierExecution,
) -> tuple[SpecimenFrontierFixtureCheck, ...]:
    expected_counts = dict(record.parameters.get("expected_counts", {}))
    required_issue_codes = tuple(
        sorted(str(item) for item in record.parameters.get("required_issue_codes", ()))
    )
    return (
        _check(
            record,
            "fixture-state",
            record.expected_state,
            _observed_fixture_state(execution),
            "fixture state matches the declared accepted or review boundary",
        ),
        _check(
            record,
            "result-state",
            record.expected_result_state,
            execution.observed_result_state,
            "adapter result state matches the fixture expectation",
        ),
        _check(
            record,
            "issue-codes",
            required_issue_codes,
            execution.issue_codes,
            "review and validation issue codes are deterministic",
        ),
        _check(
            record,
            "counts",
            expected_counts,
            {key: execution.counts.get(key, 0) for key in expected_counts},
            "operation count projection is conserved",
        ),
        _check(
            record,
            "address",
            "sha256:",
            execution.output_address,
            "sanitized operation output is content-addressed",
        ),
        _check(
            record,
            "sanitized",
            False,
            any(marker in str(execution.output).lower() for marker in ("raw_record", "patient_id")),
            "operation receipt excludes raw payload markers",
        ),
    )


def _check(
    record: SpecimenFrontierFixtureRecord,
    suffix: str,
    expected: Any,
    observed: Any,
    detail: str,
) -> SpecimenFrontierFixtureCheck:
    passed = expected == observed or (expected == "sha256:" and str(observed).startswith("sha256:"))
    return SpecimenFrontierFixtureCheck(
        check_id=f"{record.record_id}:{suffix}",
        record_id=record.record_id,
        operation=record.operation,
        check_kind=suffix,
        expected=expected,
        observed=observed,
        passed=passed,
        detail=detail,
    )


def _ontology_issue_codes(report: Any) -> tuple[str, ...]:
    codes = {issue.code for issue in report.issues}
    for mapping in report.mappings:
        if mapping.state == SpecimenEvidenceState.AMBIGUOUS:
            if any("subject" in reason for reason in mapping.reasons):
                codes.add("ambiguous_subject")
            if any("relationship" in reason for reason in mapping.reasons):
                codes.add("ambiguous_relationship")
        if mapping.state == SpecimenEvidenceState.PARTIAL:
            codes.add("missing_subject")
    return tuple(sorted(codes))


def _matched_normal_issue_codes(parsed: Any, report: Any) -> tuple[str, ...]:
    codes = {issue.code for issue in parsed.issues}
    for pair in report.pairs:
        if pair.state == SpecimenEvidenceState.AMBIGUOUS:
            codes.add("multiple_same_subject_normals")
        elif pair.state == SpecimenEvidenceState.ABSTAINED:
            if any("subject identifier" in reason for reason in pair.reasons):
                codes.add("missing_tumor_subject")
            else:
                codes.add("missing_matched_normal")
    return tuple(sorted(codes))


def _integrity_issue_codes(assessments: Any) -> tuple[str, ...]:
    codes: set[str] = set()
    for assessment in assessments:
        if assessment.state == SampleIntegrityState.FLAGGED:
            if any("subject fingerprint" in reason for reason in assessment.reasons):
                codes.add("subject_fingerprint_mismatch")
            if any("contamination" in reason for reason in assessment.reasons):
                codes.add("contamination_flag")
        elif assessment.state == SampleIntegrityState.WATCH:
            codes.add("fingerprint_watch")
        elif assessment.state == SampleIntegrityState.ABSTAINED:
            codes.add("incomplete_fingerprint")
    return tuple(sorted(codes))


__all__ = [
    "SpecimenFrontierExecution",
    "SpecimenFrontierFixtureCheck",
    "SpecimenFrontierFixtureEvaluationReport",
    "SpecimenFrontierOperationReceipt",
    "evaluate_specimen_frontier_fixture",
]
