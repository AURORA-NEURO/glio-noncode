"""Deterministic execution and sanitized receipts for Domain 05 C05–C08."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .atlas_beta import (
    AtlasBetaState,
    HistoneMarkTrackHarmonizer,
    MolecularAtlasState,
    MolecularStateAtlasAdapter,
)
from .errors import ValidationError
from .models import ReferenceContext
from .molecular_atlas_contracts import (
    MolecularAtlasContractRegistry,
    default_molecular_atlas_contracts,
)
from .molecular_atlas_public_data import (
    MOLECULAR_ATLAS_CONTEXT_KEY,
    MolecularAtlasFixture,
    MolecularAtlasOperation,
    MolecularAtlasRecord,
    MolecularAtlasRole,
    build_molecular_atlas_catalog,
    default_molecular_atlas_fixture,
    load_molecular_atlas_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class MolecularAtlasCheck:
    """One observable evaluation assertion."""

    check_id: str
    record_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasExecutionReceipt:
    """Sanitized state query or histone harmonization outcome."""

    record_id: str
    capability_id: str
    operation: MolecularAtlasOperation
    role: MolecularAtlasRole
    context_key: str
    adapter_state: str
    primary_count: int
    secondary_count: int
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
            "adapter_state",
            "expected_state",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.primary_count < 0 or self.secondary_count < 0:
            raise ValidationError("molecular atlas receipt counts cannot be negative")

    @property
    def accepted(self) -> bool:
        return self.adapter_state == self.expected_state and not set(
            self.expected_issue_codes
        ) - set(self.observed_issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasEvaluationReport:
    """Whole-fixture report with one receipt per record."""

    fixture_id: str
    fixture_version: str
    context_key: str
    catalog_address: str
    receipts: tuple[MolecularAtlasExecutionReceipt, ...]
    checks: tuple[MolecularAtlasCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    @property
    def positive_count(self) -> int:
        return sum(receipt.role is MolecularAtlasRole.POSITIVE for receipt in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(receipt.role is MolecularAtlasRole.CONTROL for receipt in self.receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


def _address(body: Any) -> str:
    return content_hash(body)


def _state_value(value: Any) -> str:
    return value.value if isinstance(value, (AtlasBetaState,)) else str(value)


def _check(check_id: str, record_id: str, passed: bool, detail: str) -> MolecularAtlasCheck:
    body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
    return MolecularAtlasCheck(check_id, record_id, passed, detail, _address(body))


def _parse_context(payload: dict[str, Any]) -> ReferenceContext:
    context = payload.get("context")
    if not isinstance(context, dict):
        raise ValidationError("molecular atlas query requires a context object")
    return ReferenceContext.from_dict(context)


def _query_issue_codes(state: str) -> tuple[str, ...]:
    return {
        "abstained": ("no_state_atlas_overlap",),
        "out_of_domain": ("state_context_mismatch",),
        "ambiguous": ("ambiguous_state_match",),
    }.get(state, ())


def _execute_state_record(
    record: MolecularAtlasRecord,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    payload = record.payload
    parser = MolecularStateAtlasAdapter()
    try:
        batch = parser.parse_text(
            payload["input_text"],
            source_id=str(payload["source_id"]),
            source_version=str(payload.get("source_version", "unspecified")),
            input_format=str(payload.get("input_format", "")) or None,
        )
    except ValidationError as exc:
        return (
            "abstained",
            0,
            0,
            ("invalid_state_atlas_input",),
            {
                "query_state": "abstained",
                "match_count": 0,
                "issue_codes": ("invalid_state_atlas_input",),
                "error_type": type(exc).__name__,
            },
        )
    base_issues = tuple(issue.code for issue in batch.issues)
    try:
        query = payload["query"]
        context = _parse_context(payload)
        if not isinstance(query, dict):
            raise ValidationError("molecular atlas query must be an object")
        result = parser.query(
            batch.records,
            molecular_state=MolecularAtlasState(str(payload["molecular_state"])),
            chromosome=str(query["chromosome"]),
            start=int(query["start"]),
            end=int(query["end"]),
            context=context,
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        issue_codes = base_issues + ("state_query_execution_error",)
        return (
            "abstained",
            len(batch.records),
            0,
            tuple(dict.fromkeys(issue_codes)),
            {
                "query_state": "abstained",
                "match_count": 0,
                "issue_codes": tuple(dict.fromkeys(issue_codes)),
                "error_type": type(exc).__name__,
            },
        )
    state = _state_value(result.state)
    issue_codes = tuple(dict.fromkeys(base_issues + _query_issue_codes(state)))
    summary = {
        "query_state": state,
        "molecular_state": result.molecular_state,
        "match_count": len(result.matches),
        "reason": result.reason,
        "issue_codes": issue_codes,
        "match_ids": tuple(match.element_id for match in result.matches),
        "context_key": context.key,
        "source_count": len({match.source_id for match in result.matches}),
        "assay_names": tuple(sorted({match.assay for match in result.matches})),
    }
    return state, len(batch.records), len(result.matches), issue_codes, summary


def _execute_histone_record(
    record: MolecularAtlasRecord,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    payload = record.payload
    harmonizer = HistoneMarkTrackHarmonizer()
    try:
        batch = harmonizer.parse_text(
            payload["input_text"],
            source_id=str(payload["source_id"]),
            source_version=str(payload.get("source_version", "unspecified")),
            input_format=str(payload.get("input_format", "")) or None,
            spread_tolerance=float(payload.get("spread_tolerance", 0.25)),
        )
    except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        issue_codes = ("invalid_histone_input",)
        return (
            "abstained",
            0,
            0,
            issue_codes,
            {
                "harmonization_state": "abstained",
                "interval_count": 0,
                "issue_codes": issue_codes,
                "error_type": type(exc).__name__,
            },
        )
    issue_codes = [issue.code for issue in batch.issues]
    if batch.state is AtlasBetaState.AMBIGUOUS:
        issue_codes.append("histone_signal_disagreement")
    elif batch.state is AtlasBetaState.PARTIAL and not batch.issues:
        issue_codes.append("histone_single_replicate")
    issue_codes = list(dict.fromkeys(issue_codes))
    state = _state_value(batch.state)
    summary = {
        "harmonization_state": state,
        "interval_count": len(batch.intervals),
        "observation_count": len(batch.observations),
        "issue_codes": tuple(issue_codes),
        "mark_names": tuple(sorted({interval.mark for interval in batch.intervals})),
        "interval_ids": tuple(interval.interval_id for interval in batch.intervals),
        "replicate_counts": tuple(
            sorted({len(interval.replicate_ids) for interval in batch.intervals})
        ),
        "signal_spreads": tuple(interval.signal_spread for interval in batch.intervals),
        "warning_count": len(batch.warnings),
        "input_hash": batch.input_hash,
    }
    return state, len(batch.observations), len(batch.intervals), tuple(issue_codes), summary


def _execute_record(
    record: MolecularAtlasRecord,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    if record.operation is MolecularAtlasOperation.HISTONE_HARMONIZATION:
        return _execute_histone_record(record)
    return _execute_state_record(record)


def evaluate_molecular_atlas_fixture(
    fixture: MolecularAtlasFixture | None = None,
    *,
    contracts: MolecularAtlasContractRegistry | None = None,
) -> MolecularAtlasEvaluationReport:
    """Execute all molecular-state and histone positive/control records."""

    selected = fixture or default_molecular_atlas_fixture()
    registry = contracts or default_molecular_atlas_contracts()
    catalog = build_molecular_atlas_catalog(selected)
    checks: list[MolecularAtlasCheck] = []
    receipts: list[MolecularAtlasExecutionReceipt] = []

    def add(check_id: str, record_id: str, passed: bool, detail: str) -> None:
        checks.append(_check(check_id, record_id, passed, detail))

    add(
        "fixture-context",
        "fixture",
        selected.context_key == MOLECULAR_ATLAS_CONTEXT_KEY,
        "fixture uses exact molecular atlas context",
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
            "contract-required fields are present",
        )
        try:
            state, primary, secondary, issue_codes, summary = _execute_record(record)
            execution_error = None
        except (TypeError, ValueError, ValidationError, KeyError, json.JSONDecodeError) as exc:
            state, primary, secondary, issue_codes, summary = (
                "invalid",
                0,
                0,
                ("execution_error",),
                {"error_type": type(exc).__name__, "issue_codes": ("execution_error",)},
            )
            execution_error = str(exc)
        check_ids = [f"{record.record_id}:contract"]
        state_check = f"{record.record_id}:state"
        add(
            state_check,
            record.record_id,
            state == record.expected_state and execution_error is None,
            "adapter state matches fixture expectation",
        )
        check_ids.append(state_check)
        issue_check = f"{record.record_id}:issues"
        add(
            issue_check,
            record.record_id,
            set(record.expected_issue_codes) <= set(issue_codes),
            "expected issue codes remain visible",
        )
        check_ids.append(issue_check)
        count_check = f"{record.record_id}:counts"
        add(
            count_check,
            record.record_id,
            primary >= 0 and secondary >= 0,
            "bounded counts are non-negative",
        )
        check_ids.append(count_check)
        role_check = f"{record.record_id}:role"
        role_ok = (record.role is MolecularAtlasRole.POSITIVE and state == "supported") or (
            record.role is MolecularAtlasRole.CONTROL and state != "supported"
        )
        add(role_check, record.record_id, role_ok, "positive and control roles remain distinct")
        check_ids.append(role_check)
        summary_check = f"{record.record_id}:summary"
        summary_ok = "issue_codes" in summary and not {"input_text", "payload", "records"} & set(
            summary
        )
        add(
            summary_check,
            record.record_id,
            summary_ok,
            "sanitized summary retains operational dimensions",
        )
        check_ids.append(summary_check)
        receipt_body = {
            "record_id": record.record_id,
            "capability_id": contract.capability_id,
            "operation": record.operation,
            "role": record.role,
            "context_key": selected.context_key,
            "adapter_state": state,
            "primary_count": primary,
            "secondary_count": secondary,
            "observed_issue_codes": issue_codes,
            "expected_state": record.expected_state,
            "expected_issue_codes": record.expected_issue_codes,
            "check_ids": tuple(check_ids),
            "summary": summary,
        }
        receipt = MolecularAtlasExecutionReceipt(
            **receipt_body, content_address=_address(receipt_body)
        )
        address_check = f"{record.record_id}:address"
        prior = tuple(check.passed for check in checks if check.record_id == record.record_id)
        add(
            address_check,
            record.record_id,
            receipt.accepted == all(prior),
            "receipt acceptance agrees with record checks",
        )
        check_ids.append(address_check)
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
        sum(item.role is MolecularAtlasRole.POSITIVE for item in receipts) == 4,
        "four positives execute",
    )
    add(
        "control-count",
        "fixture",
        sum(item.role is MolecularAtlasRole.CONTROL for item in receipts) == 12,
        "twelve controls execute",
    )
    add(
        "operation-coverage",
        "fixture",
        {item.operation for item in receipts} == set(MolecularAtlasOperation),
        "all four atlas operations execute",
    )
    add(
        "source-free-output",
        "fixture",
        all(
            not {"input_text", "records", "payload"} & set(receipt.summary) for receipt in receipts
        ),
        "receipts do not copy input collections or text",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "catalog_address": catalog.content_address,
        "receipts": receipts,
        "checks": checks,
    }
    return MolecularAtlasEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        catalog.content_address,
        tuple(receipts),
        tuple(checks),
        _address(body),
    )


def evaluate_molecular_atlas_fixture_file(path: str | Path) -> MolecularAtlasEvaluationReport:
    """Evaluate a descriptor loaded from disk."""

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return evaluate_molecular_atlas_fixture(load_molecular_atlas_fixture(payload))


__all__ = [
    "MolecularAtlasCheck",
    "MolecularAtlasEvaluationReport",
    "MolecularAtlasExecutionReceipt",
    "evaluate_molecular_atlas_fixture",
    "evaluate_molecular_atlas_fixture_file",
]
