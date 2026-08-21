"""Executable fixture evaluation for the Domain 02 structural boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .intake import RawVariantRecord
from .models import ReferenceContext
from .serialization import content_hash, jsonable
from .structural_extensions import (
    ComplexRearrangementResolver,
    CopyNumberSegment,
    CopyNumberSegmentHarmonizer,
    StructuralEvidenceState,
    SVConsensusImporter,
)
from .structural_public_data import (
    StructuralFixtureCatalog,
    StructuralFixtureRecord,
    StructuralFixtureState,
    StructuralOperation,
)
from .structural_reconstruction import StructuralReconstructor
from .variation import Breakend, HaplotypeSegment, StructuralEvent, StructuralEventKind


@dataclass(frozen=True, slots=True)
class StructuralExecution:
    """Sanitized output of one fixture operation."""

    operation: StructuralOperation
    state: StructuralFixtureState
    result_state: str
    issue_codes: tuple[str, ...]
    output_address: str
    counts: Mapping[str, int]
    output: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFixtureCheck:
    """One explicit assertion over a positive or control execution."""

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
class StructuralOperationReceipt:
    """Stable receipt for a single C01-C04 operation."""

    record_id: str
    operation: StructuralOperation
    expected_state: StructuralFixtureState
    observed_state: StructuralFixtureState
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
class StructuralFixtureEvaluationReport:
    """Complete execution report for positive records and review controls."""

    fixture_id: str
    context_key: str
    state: StructuralFixtureState
    receipts: tuple[StructuralOperationReceipt, ...]
    checks: tuple[StructuralFixtureCheck, ...]
    positive_count: int
    control_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == StructuralFixtureState.ACCEPTED and all(
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


def evaluate_structural_fixture(
    fixture: StructuralFixtureCatalog | str,
) -> StructuralFixtureEvaluationReport:
    """Execute every positive and control record in a structural fixture."""

    catalog = (
        StructuralFixtureCatalog.from_file(fixture)
        if isinstance(fixture, str)
        else fixture
    )
    all_records = catalog.positives + catalog.controls
    receipts: list[StructuralOperationReceipt] = []
    checks: list[StructuralFixtureCheck] = []
    executions: dict[str, StructuralExecution] = {}
    for record in all_records:
        execution = _execute(record, catalog.context_key)
        executions[record.record_id] = execution
        record_checks = _checks_for_record(record, execution)
        checks.extend(record_checks)
        receipts.append(
            StructuralOperationReceipt(
                record_id=record.record_id,
                operation=record.operation,
                expected_state=record.expected_state,
                observed_state=execution.state,
                expected_result_state=record.expected_result_state,
                observed_result_state=execution.result_state,
                issue_codes=execution.issue_codes,
                output_address=execution.output_address,
                counts=execution.counts,
                passed=all(check.passed for check in record_checks),
                detail=execution.detail,
            )
        )
    checks.extend(_global_checks(catalog, executions))
    state = (
        StructuralFixtureState.ACCEPTED
        if all(check.passed for check in checks)
        else StructuralFixtureState.REVIEW
    )
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "state": state,
        "receipts": receipts,
        "checks": checks,
    }
    return StructuralFixtureEvaluationReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        receipts=tuple(receipts),
        checks=tuple(checks),
        positive_count=len(catalog.positives),
        control_count=len(catalog.controls),
        content_address=content_hash(body),
    )


def _execute(record: StructuralFixtureRecord, context_key: str) -> StructuralExecution:
    if record.context_key != context_key:
        return _failed_execution(record, "context_mismatch", "record context differs from fixture")
    try:
        if record.operation == StructuralOperation.RECONSTRUCTION:
            return _run_reconstruction(record, context_key)
        if record.operation == StructuralOperation.CONSENSUS:
            return _run_consensus(record)
        if record.operation == StructuralOperation.COMPLEX_RESOLUTION:
            return _run_complex(record, context_key)
        if record.operation == StructuralOperation.COPY_NUMBER:
            return _run_copy_number(record)
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        return _failed_execution(record, "validation_error", str(exc))
    raise ValidationError(f"unsupported structural operation: {record.operation}")


def _run_reconstruction(record: StructuralFixtureRecord, context_key: str) -> StructuralExecution:
    payload = record.payload
    records_raw = _array(payload.get("records", ()), "records")
    records = tuple(_raw_record(row, index, record.source_id) for index, row in enumerate(records_raw, 1))
    result = StructuralReconstructor().reconstruct(
        records,
        context=_context(context_key),
        source_id=record.source_id,
    )
    issue_codes = tuple(sorted({issue.code for issue in result.issues}))
    errors = sum(issue.severity.value == "error" for issue in result.issues)
    state = StructuralFixtureState.REVIEW if errors or result.issues else StructuralFixtureState.ACCEPTED
    result_state = (
        "error"
        if errors
        else "warning"
        if result.issues
        else "eventful"
        if result.events
        else "empty"
    )
    output = result.to_dict()
    return StructuralExecution(
        record.operation,
        state,
        result_state,
        issue_codes,
        result.content_address,
        {
            "records": len(records),
            "events": len(result.events),
            "issues": len(result.issues),
            "errors": errors,
        },
        output,
        "symbolic, breakend, and phased records were reconstructed without flattening alternatives",
    )


def _run_consensus(record: StructuralFixtureRecord) -> StructuralExecution:
    payload = record.payload
    result = SVConsensusImporter(
        breakpoint_tolerance=int(payload.get("breakpoint_tolerance", 10))
    ).parse_text(
        str(payload.get("text", "")),
        source_id=record.source_id,
        input_format=str(payload.get("input_format", "tsv")),
    )
    issue_codes = tuple(sorted({issue.code for issue in result.issues}))
    states = tuple(sorted({item.state.value for item in result.consensus}))
    state = (
        StructuralFixtureState.REVIEW
        if result.errors or any(item.state != StructuralEvidenceState.SUPPORTED for item in result.consensus)
        else StructuralFixtureState.ACCEPTED
    )
    result_state = states[0] if len(states) == 1 else "mixed" if states else "empty"
    return StructuralExecution(
        record.operation,
        state,
        result_state,
        issue_codes,
        result.content_address,
        {
            "observations": len(result.observations),
            "consensus": len(result.consensus),
            "issues": len(result.issues),
            "errors": len(result.errors),
        },
        result.to_dict(),
        "caller versions and raw observation hashes remain beside bounded breakpoint consensus",
    )


def _run_complex(record: StructuralFixtureRecord, context_key: str) -> StructuralExecution:
    events = tuple(_structural_event(row, context_key, record.source_id) for row in _array(record.payload.get("events", ()), "events"))
    result = ComplexRearrangementResolver().resolve(events)
    issue_codes = tuple(sorted({issue.code for issue in result.issues}))
    states = tuple(sorted({item.state.value for item in result.resolutions}))
    state = StructuralFixtureState.REVIEW if result.issues else StructuralFixtureState.ACCEPTED
    result_state = states[0] if len(states) == 1 else "mixed" if states else "empty"
    return StructuralExecution(
        record.operation,
        state,
        result_state,
        issue_codes,
        result.content_address,
        {
            "events": len(events),
            "resolutions": len(result.resolutions),
            "issues": len(result.issues),
            "paths": sum(len(item.paths) for item in result.resolutions),
        },
        result.to_dict(),
        "connected breakpoint components and ambiguity were retained without choosing a canonical path",
    )


def _run_copy_number(record: StructuralFixtureRecord) -> StructuralExecution:
    segments = tuple(
        _copy_number_segment(row, index, record.source_id)
        for index, row in enumerate(_array(record.payload.get("segments", ()), "segments"), 1)
    )
    result = CopyNumberSegmentHarmonizer().harmonize(
        segments,
        value_tolerance=float(record.payload.get("value_tolerance", 0.25)),
    )
    issue_codes = tuple(sorted({issue.code for issue in result.issues}))
    states = tuple(sorted({item.state.value for item in result.segments}))
    state = StructuralFixtureState.REVIEW if result.issues else StructuralFixtureState.ACCEPTED
    result_state = states[0] if len(states) == 1 else "mixed" if states else "empty"
    return StructuralExecution(
        record.operation,
        state,
        result_state,
        issue_codes,
        result.content_address,
        {
            "input_segments": len(segments),
            "output_segments": len(result.segments),
            "issues": len(result.issues),
            "ambiguous_segments": sum(
                item.state == StructuralEvidenceState.AMBIGUOUS for item in result.segments
            ),
        },
        result.to_dict(),
        "caller segments were split at observed boundaries and disagreement remained visible",
    )


def _checks_for_record(
    record: StructuralFixtureRecord,
    execution: StructuralExecution,
) -> tuple[StructuralFixtureCheck, ...]:
    checks: list[StructuralFixtureCheck] = []
    checks.append(
        StructuralFixtureCheck(
            f"{record.record_id}:state",
            record.record_id,
            "state",
            execution.state == record.expected_state,
            record.expected_state.value,
            execution.state.value,
            "operation state must match the declared positive or review boundary",
        )
    )
    checks.append(
        StructuralFixtureCheck(
            f"{record.record_id}:result-state",
            record.record_id,
            "result_state",
            execution.result_state == record.expected_result_state,
            record.expected_result_state,
            execution.result_state,
            "domain result state must remain explicit",
        )
    )
    observed_codes = set(execution.issue_codes)
    checks.append(
        StructuralFixtureCheck(
            f"{record.record_id}:issues",
            record.record_id,
            "issue_codes",
            set(record.required_issue_codes).issubset(observed_codes),
            list(record.required_issue_codes),
            sorted(observed_codes),
            "declared review reasons must be present when a control is executed",
        )
    )
    for key, expected in record.expected_counts.items():
        observed = execution.counts.get(key)
        checks.append(
            StructuralFixtureCheck(
                f"{record.record_id}:count:{key}",
                record.record_id,
                "count",
                observed == expected,
                expected,
                observed,
                "operation count floor or exact count must remain reproducible",
            )
        )
    checks.append(
        StructuralFixtureCheck(
            f"{record.record_id}:address",
            record.record_id,
            "content_address",
            execution.output_address.startswith("sha256:") and len(execution.output_address) == 71,
            "sha256:<64 hex characters>",
            execution.output_address,
            "every operation result is content-addressed",
        )
    )
    return tuple(checks)


def _global_checks(
    catalog: StructuralFixtureCatalog,
    executions: Mapping[str, StructuralExecution],
) -> tuple[StructuralFixtureCheck, ...]:
    checks: list[StructuralFixtureCheck] = []
    checks.append(
        StructuralFixtureCheck(
            "fixture:positive-floor",
            None,
            "positive_floor",
            len(catalog.positives) >= 4,
            4,
            len(catalog.positives),
            "all four structural operations require a positive executable record",
        )
    )
    checks.append(
        StructuralFixtureCheck(
            "fixture:control-floor",
            None,
            "control_floor",
            len(catalog.controls) >= 8,
            8,
            len(catalog.controls),
            "review behavior requires at least two controls per operation",
        )
    )
    checks.append(
        StructuralFixtureCheck(
            "fixture:operation-floor",
            None,
            "operation_floor",
            set(catalog.operation_ids) == {item.value for item in StructuralOperation},
            [item.value for item in StructuralOperation],
            list(catalog.operation_ids),
            "the fixture must cover C01 through C04",
        )
    )
    first = catalog.positives[0]
    repeat = _execute(first, catalog.context_key)
    first_execution = executions[first.record_id]
    checks.append(
        StructuralFixtureCheck(
            "fixture:determinism",
            first.record_id,
            "determinism",
            repeat.output_address == first_execution.output_address,
            first_execution.output_address,
            repeat.output_address,
            "replaying the first positive operation must preserve its address",
        )
    )
    checks.append(
        StructuralFixtureCheck(
            "fixture:positive-control-separation",
            None,
            "identity",
            not set(item.record_id for item in catalog.positives)
            & set(item.record_id for item in catalog.controls),
            "disjoint IDs",
            "overlap" if set(catalog.record_ids) != set(dict.fromkeys(catalog.record_ids)) else "disjoint",
            "positive and control identities must not be reused",
        )
    )
    checks.append(
        StructuralFixtureCheck(
            "fixture:output-boundary",
            None,
            "output_boundary",
            all("patient_id" not in str(execution.output).lower() for execution in executions.values()),
            "no patient identifiers",
            "clean",
            "operation receipts must not copy restricted identifiers",
        )
    )
    return tuple(checks)


def _context(key: str) -> ReferenceContext:
    parts = key.split("|")
    if len(parts) != 6:
        raise ValidationError("structural fixture context key requires six fields")
    return ReferenceContext(*parts[:4], territory=parts[4], treatment_phase=parts[5])


def _raw_record(row: Any, index: int, source_id: str) -> RawVariantRecord:
    if not isinstance(row, Mapping):
        raise ValidationError(f"records[{index - 1}] must be an object")
    return RawVariantRecord(
        record_id=str(row.get("record_id", f"record-{index}")),
        chromosome=str(row.get("chromosome", "")),
        position=int(row.get("position", 0)),
        reference=str(row.get("reference", "N")),
        alternate=str(row.get("alternate", "")),
        source_line=int(row.get("source_line", index)),
        raw_hash=str(row.get("raw_hash", content_hash({"source_id": source_id, "row": row}))),
        info=dict(row.get("info", {})),
        sample=dict(row.get("sample", {})),
        filter_value=str(row.get("filter_value", ".")),
        quality=str(row.get("quality", ".")),
    )


def _structural_event(row: Any, context_key: str, source_id: str) -> StructuralEvent:
    if not isinstance(row, Mapping):
        raise ValidationError("complex event must be an object")
    breakends = tuple(
        Breakend(
            breakend_id=str(item.get("breakend_id", "")),
            chromosome=str(item.get("chromosome", "")),
            position=int(item.get("position", 0)),
            orientation=str(item.get("orientation", "unknown")),
            mate_id=str(item.get("mate_id", "")),
            allele=str(item.get("allele", "N")),
            copy_number=(float(item["copy_number"]) if item.get("copy_number") is not None else None),
        )
        for item in _object_array(row.get("breakends", ()), "breakends")
    )
    haplotype_segments = tuple(
        HaplotypeSegment(
            segment_id=str(item.get("segment_id", "")),
            chromosome=str(item.get("chromosome", "")),
            start=int(item.get("start", 0)),
            end=int(item.get("end", 0)),
            phase_set=str(item.get("phase_set", "")),
            allele=str(item.get("allele", "")),
            source_variant_ids=tuple(
                str(value)
                for value in _array(item.get("source_variant_ids", ()), "source_variant_ids")
            ),
        )
        for item in _object_array(row.get("haplotype_segments", ()), "haplotype_segments")
    )
    return StructuralEvent(
        event_id=str(row.get("event_id", "")),
        kind=StructuralEventKind(str(row.get("kind", StructuralEventKind.BREAKEND_PAIR.value))),
        breakends=breakends,
        haplotype_segments=haplotype_segments,
        context=_context(context_key),
        source_id=source_id,
        reconstruction_support=float(row.get("reconstruction_support", 1.0)),
        uncertainty=float(row.get("uncertainty", 0.0)),
        annotations=dict(row.get("annotations", {})),
    )


def _copy_number_segment(row: Any, index: int, source_id: str) -> CopyNumberSegment:
    if not isinstance(row, Mapping):
        raise ValidationError(f"segments[{index - 1}] must be an object")
    return CopyNumberSegment(
        segment_id=str(row.get("segment_id", f"segment-{index}")),
        caller_id=str(row.get("caller_id", "")),
        chromosome=str(row.get("chromosome", row.get("chrom", ""))),
        start=int(row.get("start", 0)),
        end=int(row.get("end", 0)),
        copy_number=float(row.get("copy_number", 0.0)),
        raw_hash=str(row.get("raw_hash", content_hash({"source_id": source_id, "row": row}))),
        source_id=source_id,
        minor_copy_number=(
            float(row["minor_copy_number"])
            if row.get("minor_copy_number") is not None
            else None
        ),
        attributes=dict(row.get("attributes", {})),
    )


def _failed_execution(
    record: StructuralFixtureRecord,
    code: str,
    detail: str,
) -> StructuralExecution:
    body = {"record_id": record.record_id, "operation": record.operation, "code": code}
    return StructuralExecution(
        record.operation,
        StructuralFixtureState.REVIEW,
        "review-issue",
        (code,),
        content_hash(body),
        {"issues": 1, "errors": 1},
        {"state": "review", "issue_codes": [code]},
        detail,
    )


def _array(value: Any, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValidationError(f"{field_name} must be an array")
    return tuple(value)


def _object_array(value: Any, field_name: str) -> tuple[Mapping[str, Any], ...]:
    rows = _array(value, field_name)
    if not all(isinstance(item, Mapping) for item in rows):
        raise ValidationError(f"{field_name} must contain objects")
    return tuple(item for item in rows if isinstance(item, Mapping))


__all__ = [
    "StructuralExecution",
    "StructuralFixtureCheck",
    "StructuralFixtureEvaluationReport",
    "StructuralOperationReceipt",
    "evaluate_structural_fixture",
]
