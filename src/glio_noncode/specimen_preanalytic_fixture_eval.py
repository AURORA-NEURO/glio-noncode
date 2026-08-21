"""Fixture execution and sanitized receipts for Domain 03 C13-C16.

The evaluator routes each aggregate record through the existing bounded
frontier adapter, then emits only a typed receipt and a compact result summary.
Raw payloads remain on the catalog side of the boundary. Every operation has
its own dispatch path, expected-state comparison, issue-code comparison, and
output-address check so a passing aggregate result is more than a smoke test.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import (
    AssayLineageProtocolTracker,
    BiospecimenPreanalyticQualityAssessor,
    FrontierState,
    IdentityConflictAdjudicator,
    SpecimenContextEnvelopePublisher,
)
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_preanalytic_public_data import (
    SpecimenPreanalyticFixtureCatalog,
    SpecimenPreanalyticOperation,
    SpecimenPreanalyticRecord,
    SpecimenPreanalyticRole,
    audit_specimen_preanalytic_data,
)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticExecutionCheck:
    """One check attached to a single sanitized execution receipt."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticReceipt:
    """Sanitized result for one fixture record."""

    record_id: str
    operation: str
    role: str
    context_key: str
    source_ids: tuple[str, ...]
    expected_state: str
    observed_state: str
    issue_codes: tuple[str, ...]
    summary: Mapping[str, Any]
    checks: tuple[SpecimenPreanalyticExecutionCheck, ...]
    output_address: str
    passed: bool

    def __post_init__(self) -> None:
        for field in (
            "record_id",
            "operation",
            "role",
            "context_key",
            "expected_state",
            "observed_state",
            "output_address",
        ):
            require_non_empty(str(getattr(self, field)), f"receipt {field}")
        if not self.source_ids:
            raise ValidationError("receipt source IDs must not be empty")
        if not self.output_address.startswith("sha256:"):
            raise ValidationError("receipt output address must be sha256-prefixed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticEvaluationReport:
    """Aggregate fixture evaluation report."""

    fixture_id: str
    fixture_context_key: str
    state: str
    receipts: tuple[SpecimenPreanalyticReceipt, ...]
    checks: tuple[SpecimenPreanalyticExecutionCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(sorted({receipt.operation for receipt in self.receipts}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
            "receipt_count": len(self.receipts),
            "operation_ids": self.operation_ids,
        }


def evaluate_specimen_preanalytic_fixture(
    catalog: SpecimenPreanalyticFixtureCatalog,
) -> SpecimenPreanalyticEvaluationReport:
    """Execute all C13-C16 records and retain explicit boundary checks."""

    data_audit = audit_specimen_preanalytic_data(catalog)
    receipts: list[SpecimenPreanalyticReceipt] = []
    checks: list[SpecimenPreanalyticExecutionCheck] = [
        _check(
            "data-boundary",
            data_audit.passed,
            data_audit.state,
            "accepted",
            "catalog boundary passes",
        ),
        _check(
            "fixture-record-floor",
            len(catalog.records) == 12,
            len(catalog.records),
            12,
            "fixture record floor",
        ),
        _check(
            "fixture-positive-floor",
            len(catalog.positives) == 4,
            len(catalog.positives),
            4,
            "positive record floor",
        ),
        _check(
            "fixture-control-floor",
            len(catalog.controls) == 8,
            len(catalog.controls),
            8,
            "control record floor",
        ),
        _check(
            "operation-floor",
            set(catalog.operation_ids) == {item.value for item in SpecimenPreanalyticOperation},
            catalog.operation_ids,
            tuple(item.value for item in SpecimenPreanalyticOperation),
            "operation coverage",
        ),
    ]
    for record in catalog.records:
        receipt, record_checks = _evaluate_record(record, catalog)
        receipts.append(receipt)
        checks.extend(record_checks)
    checks.extend(
        (
            _check(
                "receipt-identity",
                len({receipt.record_id for receipt in receipts}) == len(receipts),
                tuple(receipt.record_id for receipt in receipts),
                "unique receipt IDs",
                "receipt identity is unique",
            ),
            _check(
                "receipt-floor",
                len(receipts) == len(catalog.records),
                len(receipts),
                len(catalog.records),
                "one receipt per input record",
            ),
            _check(
                "receipt-addresses",
                all(receipt.output_address.startswith("sha256:") for receipt in receipts),
                True,
                True,
                "all receipts are addressed",
            ),
            _check(
                "receipt-sanitation",
                not _forbidden_keys(receipts),
                True,
                True,
                "receipts contain no forbidden keys",
            ),
            _check(
                "positive-results",
                all(
                    receipt.passed
                    for receipt in receipts
                    if receipt.role == SpecimenPreanalyticRole.POSITIVE.value
                ),
                True,
                True,
                "positive records pass",
            ),
            _check(
                "control-results",
                all(
                    receipt.passed
                    for receipt in receipts
                    if receipt.role == SpecimenPreanalyticRole.CONTROL.value
                ),
                True,
                True,
                "controls match review expectations",
            ),
        )
    )
    state = "accepted" if all(check.passed for check in checks) else "review"
    body = {
        "fixture_id": catalog.fixture_id,
        "fixture_context_key": catalog.context_key,
        "state": state,
        "receipts": receipts,
        "checks": checks,
    }
    return SpecimenPreanalyticEvaluationReport(
        catalog.fixture_id,
        catalog.context_key,
        state,
        tuple(receipts),
        tuple(checks),
        content_hash(body),
    )


def _evaluate_record(
    record: SpecimenPreanalyticRecord,
    catalog: SpecimenPreanalyticFixtureCatalog,
) -> tuple[SpecimenPreanalyticReceipt, tuple[SpecimenPreanalyticExecutionCheck, ...]]:
    operation = record.operation
    issue_codes: tuple[str, ...]
    observed_state: FrontierState
    summary: dict[str, Any]
    try:
        if operation == SpecimenPreanalyticOperation.PREANALYTIC_QUALITY:
            observed_state, issue_codes, summary = _run_quality(record)
        elif operation == SpecimenPreanalyticOperation.ASSAY_LINEAGE:
            observed_state, issue_codes, summary = _run_lineage(record)
        elif operation == SpecimenPreanalyticOperation.IDENTITY_ADJUDICATION:
            observed_state, issue_codes, summary = _run_identity(record)
        elif operation == SpecimenPreanalyticOperation.CONTEXT_ENVELOPE:
            observed_state, issue_codes, summary = _run_envelope(record)
        else:  # pragma: no cover - enum construction prevents this branch
            raise ValidationError(f"unsupported operation {operation}")
    except Exception as exc:  # retain invalid controls as review receipts
        observed_state = FrontierState.REVIEW
        issue_codes = ("execution_error",)
        summary = {"error_type": type(exc).__name__, "error_message": str(exc)}
    output_body = {
        "record_id": record.record_id,
        "operation": operation.value,
        "observed_state": observed_state.value,
        "issue_codes": issue_codes,
        "summary": summary,
    }
    output_address = content_hash(output_body)
    checks = (
        _check(
            f"{record.record_id}:operation",
            operation.value in {item.value for item in SpecimenPreanalyticOperation},
            operation.value,
            "declared operation",
            "operation dispatch",
        ),
        _check(
            f"{record.record_id}:context",
            record.context_key == catalog.context_key,
            record.context_key,
            catalog.context_key,
            "record context matches fixture",
        ),
        _check(
            f"{record.record_id}:source-set",
            set(record.source_ids).issubset(set(catalog.source_ids)),
            record.source_ids,
            catalog.source_ids,
            "record sources are declared",
        ),
        _check(
            f"{record.record_id}:expected-state",
            record.expected_state.value in {"accepted", "published", "review"},
            record.expected_state.value,
            "accepted/published/review",
            "expected state is contractual",
        ),
        _check(
            f"{record.record_id}:observed-state",
            observed_state.value == record.expected_state.value,
            observed_state.value,
            record.expected_state.value,
            "adapter state matches fixture expectation",
        ),
        _check(
            f"{record.record_id}:role-state",
            _role_state_is_conservative(record, observed_state),
            (record.role.value, observed_state.value),
            "positive accepted/published; control review",
            "role state is conservative",
        ),
        _check(
            f"{record.record_id}:issue-codes",
            set(record.expected_issue_codes).issubset(set(issue_codes)),
            issue_codes,
            record.expected_issue_codes,
            "declared issue codes are retained",
        ),
        _check(
            f"{record.record_id}:address",
            output_address.startswith("sha256:"),
            output_address,
            "sha256:<digest>",
            "result is content-addressed",
        ),
        _check(
            f"{record.record_id}:summary",
            isinstance(summary, Mapping),
            type(summary).__name__,
            "mapping",
            "result summary is structured",
        ),
        _check(
            f"{record.record_id}:sanitized",
            not _forbidden_keys(summary),
            True,
            True,
            "result summary is sanitized",
        ),
    )
    passed = all(check.passed for check in checks)
    receipt = SpecimenPreanalyticReceipt(
        record.record_id,
        operation.value,
        record.role.value,
        record.context_key,
        record.source_ids,
        record.expected_state.value,
        observed_state.value,
        tuple(sorted(set(issue_codes))),
        summary,
        checks,
        output_address,
        passed,
    )
    return receipt, checks


def _run_quality(
    record: SpecimenPreanalyticRecord,
) -> tuple[FrontierState, tuple[str, ...], dict[str, Any]]:
    payload = dict(record.payload)
    rows = _rows(payload, "records")
    thresholds = payload.get("thresholds")
    report = BiospecimenPreanalyticQualityAssessor().assess(
        rows,
        context_key=record.context_key,
        source_id=record.source_ids[0],
        thresholds=thresholds if isinstance(thresholds, Mapping) else None,
    )
    issue_codes = _issue_codes(item.issues for item in report.observations)
    observed = (
        FrontierState.ACCEPTED
        if not report.review_ids and report.pass_ids
        else FrontierState.REVIEW
    )
    return (
        observed,
        issue_codes,
        {
            "pass_ids": report.pass_ids,
            "review_ids": report.review_ids,
            "observation_count": len(report.observations),
            "quality_scores": tuple(round(item.quality_score, 6) for item in report.observations),
            "failed_metrics": tuple(
                sorted({metric for item in report.observations for metric in item.failed_metrics})
            ),
            "adapter_address": report.content_address,
        },
    )


def _run_lineage(
    record: SpecimenPreanalyticRecord,
) -> tuple[FrontierState, tuple[str, ...], dict[str, Any]]:
    report = AssayLineageProtocolTracker().track(
        _rows(dict(record.payload), "nodes"),
        context_key=record.context_key,
    )
    issue_codes = _issue_codes(item.issues for item in report.nodes)
    observed = (
        FrontierState.ACCEPTED
        if not report.conflict_ids
        and all(item.state == FrontierState.ACCEPTED for item in report.nodes)
        else FrontierState.REVIEW
    )
    return (
        observed,
        issue_codes,
        {
            "node_count": len(report.nodes),
            "root_ids": report.root_ids,
            "conflict_ids": report.conflict_ids,
            "node_states": tuple(item.state.value for item in report.nodes),
            "adapter_address": report.content_address,
        },
    )


def _run_identity(
    record: SpecimenPreanalyticRecord,
) -> tuple[FrontierState, tuple[str, ...], dict[str, Any]]:
    payload = dict(record.payload)
    report = IdentityConflictAdjudicator().adjudicate(
        _rows(payload, "observations"),
        context_key=record.context_key,
        minimum_agreement=float(payload.get("minimum_agreement", 0.8)),
    )
    issue_codes = _issue_codes(item.issues for item in report.decisions)
    observed = (
        FrontierState.ACCEPTED
        if not report.review_ids and report.accepted_ids
        else FrontierState.REVIEW
    )
    return (
        observed,
        issue_codes,
        {
            "accepted_ids": report.accepted_ids,
            "review_ids": report.review_ids,
            "decision_count": len(report.decisions),
            "agreements": tuple(round(item.agreement, 6) for item in report.decisions),
            "adapter_address": report.content_address,
        },
    )


def _run_envelope(
    record: SpecimenPreanalyticRecord,
) -> tuple[FrontierState, tuple[str, ...], dict[str, Any]]:
    payload = record.payload
    issue_codes: list[str] = []
    if (
        _text(payload.get("context_key"))
        and _text(payload.get("context_key")) != record.context_key
    ):
        issue_codes.append("envelope_context_mismatch")
    specimen_ids = payload.get("specimen_ids", ())
    if (
        not isinstance(specimen_ids, Sequence)
        or isinstance(specimen_ids, (str, bytes, bytearray))
        or not specimen_ids
    ):
        issue_codes.append("missing_specimen_ids")
    receipt_fields = ("lineage_address", "quality_address", "identity_address")
    for field in receipt_fields:
        value = _text(payload.get(field))
        if not value:
            issue_codes.append(f"missing_{field}")
        elif not value.startswith("sha256:"):
            issue_codes.append(f"invalid_{field}")
    if issue_codes:
        return (
            FrontierState.REVIEW,
            tuple(sorted(issue_codes)),
            {
                "envelope_id": _text(payload.get("envelope_id")),
                "specimen_count": len(specimen_ids)
                if isinstance(specimen_ids, Sequence)
                and not isinstance(specimen_ids, (str, bytes, bytearray))
                else 0,
                "receipt_field_count": sum(
                    bool(_text(payload.get(field))) for field in receipt_fields
                ),
            },
        )
    envelope = SpecimenContextEnvelopePublisher().publish(
        envelope_id=_text(payload.get("envelope_id")),
        context_key=record.context_key,
        specimen_ids=tuple(str(item) for item in specimen_ids),
        lineage_address=_text(payload.get("lineage_address")),
        quality_address=_text(payload.get("quality_address")),
        identity_address=_text(payload.get("identity_address")),
    )
    return (
        envelope.state,
        (),
        {
            "envelope_id": envelope.envelope_id,
            "specimen_ids": envelope.specimen_ids,
            "publication_address": envelope.publication_address,
            "receipt_field_count": len(receipt_fields),
        },
    )


def _rows(payload: Mapping[str, Any], key: str) -> tuple[Mapping[str, Any], ...]:
    value = payload.get(key)
    if value is None:
        return (payload,)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValidationError(f"{key} must be a list")
    return tuple(item for item in value if isinstance(item, Mapping))


def _issue_codes(groups: Any) -> tuple[str, ...]:
    return tuple(sorted({issue.code for group in groups for issue in group}))


def _role_state_is_conservative(record: SpecimenPreanalyticRecord, observed: FrontierState) -> bool:
    if record.role == SpecimenPreanalyticRole.POSITIVE:
        return observed.value in {"accepted", "published"}
    return observed == FrontierState.REVIEW


def _check(
    check_id: str, passed: bool, observed: Any, expected: Any, message: str
) -> SpecimenPreanalyticExecutionCheck:
    return SpecimenPreanalyticExecutionCheck(check_id, bool(passed), observed, expected, message)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _forbidden_keys(value: Any) -> tuple[str, ...]:
    forbidden = {
        "records",
        "raw_records",
        "payload",
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
        "case_uuid",
        "individual_id",
        "person_id",
    }
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in forbidden:
                found.add(normalized)
            found.update(_forbidden_keys(nested))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            found.update(_forbidden_keys(nested))
    return tuple(sorted(found))


__all__ = [
    "SpecimenPreanalyticEvaluationReport",
    "SpecimenPreanalyticExecutionCheck",
    "SpecimenPreanalyticReceipt",
    "evaluate_specimen_preanalytic_fixture",
]
