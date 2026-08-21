"""Deterministic execution and evidence receipts for C05–C08."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .reference_annotation_contracts import (
    ReferenceAnnotationContractRegistry,
    default_reference_annotation_contracts,
)
from .reference_annotation_public_data import (
    REFERENCE_ANNOTATION_CONTEXT_KEY,
    ReferenceAnnotationFixture,
    ReferenceAnnotationOperation,
    ReferenceAnnotationRecord,
    ReferenceAnnotationRole,
    build_reference_annotation_catalog,
    default_reference_annotation_fixture,
    load_reference_annotation_fixture,
)
from .reference_beta import (
    DiseaseOntologyMapper,
    GencodeTranscriptAdapter,
    ManeTranscriptAdapter,
    ReferenceBetaState,
    RegulatoryOntologyAdapter,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationCheck:
    """One observable evaluation assertion."""

    check_id: str
    record_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationExecutionReceipt:
    """Sanitized operation result retaining counts, states, and issue codes."""

    record_id: str
    capability_id: str
    operation: ReferenceAnnotationOperation
    role: ReferenceAnnotationRole
    context_key: str
    catalog_state: str
    catalog_count: int
    resolution_state: str
    match_count: int
    observed_issue_codes: tuple[str, ...]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    check_ids: tuple[str, ...]
    summary: dict[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "capability_id",
            "context_key",
            "catalog_state",
            "resolution_state",
            "expected_state",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.catalog_count < 0 or self.match_count < 0:
            raise ValidationError("annotation counts cannot be negative")

    @property
    def accepted(self) -> bool:
        return self.expected_state == self.resolution_state and not set(
            self.expected_issue_codes
        ) - set(self.observed_issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationEvaluationReport:
    """Whole-fixture report with per-record receipts and explicit checks."""

    fixture_id: str
    fixture_version: str
    context_key: str
    catalog_address: str
    receipts: tuple[ReferenceAnnotationExecutionReceipt, ...]
    checks: tuple[ReferenceAnnotationCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    @property
    def positive_count(self) -> int:
        return sum(receipt.role is ReferenceAnnotationRole.POSITIVE for receipt in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(receipt.role is ReferenceAnnotationRole.CONTROL for receipt in self.receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


def _address(body: Any) -> str:
    return content_hash(body)


def _state_value(value: ReferenceBetaState | str) -> str:
    return value.value if isinstance(value, ReferenceBetaState) else str(value)


def _check(
    check_id: str,
    record_id: str,
    passed: bool,
    detail: str,
) -> ReferenceAnnotationCheck:
    body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
    return ReferenceAnnotationCheck(check_id, record_id, passed, detail, _address(body))


def _record_issue_codes(
    record: ReferenceAnnotationRecord, catalog: Any, result: Any
) -> tuple[str, ...]:
    values = [issue.code for issue in getattr(catalog, "issues", ())]
    values.extend(issue.code for issue in getattr(result, "issues", ()))
    if result.state is ReferenceBetaState.AMBIGUOUS:
        values.append(
            {
                ReferenceAnnotationOperation.GENCODE_TRANSCRIPT: "ambiguous_transcript_match",
                ReferenceAnnotationOperation.MANE_TRANSCRIPT: "ambiguous_mane_match",
                ReferenceAnnotationOperation.REGULATORY_ONTOLOGY: "term_match_ambiguous",
                ReferenceAnnotationOperation.DISEASE_ONTOLOGY: "disease_mapping_ambiguous",
            }[record.operation]
        )
    if result.state is ReferenceBetaState.ABSTAINED:
        values.append(
            {
                ReferenceAnnotationOperation.GENCODE_TRANSCRIPT: "transcript_not_resolved",
                ReferenceAnnotationOperation.MANE_TRANSCRIPT: "mane_not_resolved",
                ReferenceAnnotationOperation.REGULATORY_ONTOLOGY: "term_not_resolved",
                ReferenceAnnotationOperation.DISEASE_ONTOLOGY: "disease_not_resolved",
            }[record.operation]
        )
    return tuple(dict.fromkeys(values))


def _execute_record(
    record: ReferenceAnnotationRecord,
) -> tuple[str, int, str, int, tuple[str, ...], dict[str, Any]]:
    payload = record.payload
    input_text = payload.get("input_text")
    input_format = payload.get("input_format")
    query = payload.get("query")
    if not isinstance(input_text, str) or not isinstance(query, dict):
        raise ValidationError(f"record {record.record_id} has invalid execution payload")
    if record.operation is ReferenceAnnotationOperation.GENCODE_TRANSCRIPT:
        adapter = GencodeTranscriptAdapter()
        catalog = adapter.parse_text(
            input_text,
            source_id="fixture-gencode",
            source_version="fixture",
            assembly=str(payload.get("assembly", "GRCh38")),
            input_format=input_format,
        )
        result = adapter.resolve(catalog, **query)
        summary = {
            "catalog_state": _state_value(catalog.state),
            "record_count": len(catalog.records),
            "resolution_state": _state_value(result.state),
            "match_count": len(result.records),
            "issue_codes": _record_issue_codes(record, catalog, result),
            "transcript_ids": tuple(item.versioned_id for item in result.records),
        }
        return (
            summary["catalog_state"],
            summary["record_count"],
            summary["resolution_state"],
            summary["match_count"],
            summary["issue_codes"],
            summary,
        )
    if record.operation is ReferenceAnnotationOperation.MANE_TRANSCRIPT:
        adapter = ManeTranscriptAdapter()
        catalog = adapter.parse_text(
            input_text,
            source_id="fixture-mane",
            source_version="fixture",
            input_format=input_format,
        )
        result = adapter.resolve(catalog, **query)
        summary = {
            "catalog_state": "partial" if catalog.issues else "supported",
            "record_count": len(catalog.records),
            "resolution_state": _state_value(result.state),
            "match_count": len(result.records),
            "issue_codes": _record_issue_codes(record, catalog, result),
            "mane_statuses": tuple(item.mane_status for item in result.records),
        }
        return (
            summary["catalog_state"],
            summary["record_count"],
            summary["resolution_state"],
            summary["match_count"],
            summary["issue_codes"],
            summary,
        )
    if record.operation is ReferenceAnnotationOperation.REGULATORY_ONTOLOGY:
        adapter = RegulatoryOntologyAdapter()
        catalog = adapter.parse_text(
            input_text,
            source_id="fixture-ro",
            source_version="fixture",
            input_format=input_format,
        )
        result = adapter.normalize(query, catalog=catalog)
        summary = {
            "catalog_state": "partial" if catalog.issues else "supported",
            "term_count": len(catalog.terms),
            "resolution_state": _state_value(result.state),
            "match_count": len(result.matches),
            "issue_codes": _record_issue_codes(record, catalog, result),
            "term_ids": tuple(match.term.term_id for match in result.matches),
        }
        return (
            summary["catalog_state"],
            summary["term_count"],
            summary["resolution_state"],
            summary["match_count"],
            summary["issue_codes"],
            summary,
        )
    if record.operation is ReferenceAnnotationOperation.DISEASE_ONTOLOGY:
        mapper = DiseaseOntologyMapper()
        catalog = mapper.parse_text(
            input_text,
            source_id="fixture-mondo",
            source_version="fixture",
            input_format=input_format,
        )
        result = mapper.map(query, catalog=catalog)
        summary = {
            "catalog_state": "partial" if catalog.issues else "supported",
            "mapping_count": len(catalog.mappings),
            "resolution_state": _state_value(result.state),
            "match_count": len(result.mappings),
            "issue_codes": _record_issue_codes(record, catalog, result),
            "target_ids": tuple(mapping.target_term_id for mapping in result.mappings),
        }
        return (
            summary["catalog_state"],
            summary["mapping_count"],
            summary["resolution_state"],
            summary["match_count"],
            summary["issue_codes"],
            summary,
        )
    raise ValidationError(f"unsupported annotation operation: {record.operation}")


def evaluate_reference_annotation_fixture(
    fixture: ReferenceAnnotationFixture | None = None,
    *,
    contracts: ReferenceAnnotationContractRegistry | None = None,
) -> ReferenceAnnotationEvaluationReport:
    """Execute every positive and control record against the existing adapters."""

    selected = fixture or default_reference_annotation_fixture()
    registry = contracts or default_reference_annotation_contracts()
    catalog = build_reference_annotation_catalog(selected)
    checks: list[ReferenceAnnotationCheck] = []
    receipts: list[ReferenceAnnotationExecutionReceipt] = []

    def add(check_id: str, record_id: str, passed: bool, detail: str) -> None:
        checks.append(_check(check_id, record_id, passed, detail))

    add(
        "fixture-context",
        "fixture",
        selected.context_key == REFERENCE_ANNOTATION_CONTEXT_KEY,
        "fixture uses the exact annotation context",
    )
    add(
        "fixture-address",
        "fixture",
        selected.content_address
        == _address(
            {key: value for key, value in selected.to_dict().items() if key != "content_address"}
        ),
        "fixture address verifies",
    )
    catalog_body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "source_ids": catalog.source_ids,
        "record_ids": catalog.record_ids,
        "operations": catalog.operations,
    }
    add(
        "catalog-address",
        "fixture",
        catalog.content_address == _address(catalog_body),
        "catalog address verifies",
    )
    for record in selected.records:
        contract = registry.by_operation(record.operation)
        missing = contract.validate_payload(record.payload)
        add(
            f"{record.record_id}:contract",
            record.record_id,
            not missing,
            "required execution fields are present",
        )
        try:
            catalog_state, count, result_state, match_count, issue_codes, summary = _execute_record(
                record
            )
            execution_error = None
        except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            catalog_state, count, result_state, match_count, issue_codes, summary = (
                "invalid",
                0,
                "abstained",
                0,
                ("execution_error",),
                {"error_type": type(exc).__name__},
            )
            execution_error = str(exc)
        expected_issue_codes = tuple(record.expected_issue_codes)
        check_ids = [f"{record.record_id}:contract"]
        check_id = f"{record.record_id}:state"
        add(
            check_id,
            record.record_id,
            result_state == record.expected_state and execution_error is None,
            "resolution state matches the fixture expectation",
        )
        check_ids.append(check_id)
        check_id = f"{record.record_id}:issues"
        add(
            check_id,
            record.record_id,
            set(expected_issue_codes) <= set(issue_codes),
            "expected issue codes remain visible",
        )
        check_ids.append(check_id)
        check_id = f"{record.record_id}:count"
        add(
            check_id,
            record.record_id,
            count >= match_count,
            "match count does not exceed catalog count",
        )
        check_ids.append(check_id)
        check_id = f"{record.record_id}:role"
        role_ok = (
            record.role is ReferenceAnnotationRole.POSITIVE and result_state == "supported"
        ) or (record.role is ReferenceAnnotationRole.CONTROL and result_state != "supported")
        add(
            check_id,
            record.record_id,
            role_ok,
            "positive and control role boundaries are respected",
        )
        check_ids.append(check_id)
        check_id = f"{record.record_id}:summary"
        summary_ok = all(
            key in summary
            for key in ("catalog_state", "resolution_state", "match_count", "issue_codes")
        )
        add(
            check_id,
            record.record_id,
            summary_ok,
            "sanitized summary retains operational dimensions",
        )
        check_ids.append(check_id)
        check_id = f"{record.record_id}:address"
        receipt_body = {
            "record_id": record.record_id,
            "capability_id": contract.capability_id,
            "operation": record.operation,
            "role": record.role,
            "context_key": selected.context_key,
            "catalog_state": catalog_state,
            "catalog_count": count,
            "resolution_state": result_state,
            "match_count": match_count,
            "observed_issue_codes": issue_codes,
            "expected_state": record.expected_state,
            "expected_issue_codes": expected_issue_codes,
            "check_ids": tuple(check_ids),
            "summary": summary,
        }
        receipt = ReferenceAnnotationExecutionReceipt(
            **receipt_body,
            content_address=_address(receipt_body),
        )
        add(
            check_id,
            record.record_id,
            receipt.accepted
            == all(check.passed for check in checks if check.record_id == record.record_id),
            "receipt acceptance agrees with record checks",
        )
        check_ids.append(check_id)
        receipts.append(receipt)
    add(
        "receipt-count",
        "fixture",
        len(receipts) == len(selected.records),
        "one receipt is emitted per record",
    )
    add(
        "positive-count",
        "fixture",
        sum(item.role is ReferenceAnnotationRole.POSITIVE for item in receipts) == 4,
        "four positives are executed",
    )
    add(
        "control-count",
        "fixture",
        sum(item.role is ReferenceAnnotationRole.CONTROL for item in receipts) == 12,
        "twelve controls are executed",
    )
    add(
        "operation-coverage",
        "fixture",
        {item.operation for item in receipts} == set(ReferenceAnnotationOperation),
        "all four operation families execute",
    )
    add(
        "source-free-output",
        "fixture",
        all("input_text" not in receipt.summary for receipt in receipts),
        "receipts do not copy input text",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "catalog_address": catalog.content_address,
        "receipts": receipts,
        "checks": checks,
    }
    return ReferenceAnnotationEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        catalog.content_address,
        tuple(receipts),
        tuple(checks),
        _address(body),
    )


def evaluate_reference_annotation_fixture_file(
    path: str | Path,
) -> ReferenceAnnotationEvaluationReport:
    """Evaluate a JSON fixture from disk."""

    fixture_path = Path(path)
    with fixture_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return evaluate_reference_annotation_fixture(load_reference_annotation_fixture(payload))


__all__ = [
    "ReferenceAnnotationCheck",
    "ReferenceAnnotationEvaluationReport",
    "ReferenceAnnotationExecutionReceipt",
    "evaluate_reference_annotation_fixture",
    "evaluate_reference_annotation_fixture_file",
]
