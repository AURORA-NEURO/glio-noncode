"""Deterministic execution and sanitized receipts for Domain 05 C01–C04."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .atlas_extensions import CcreAtlasAdapter, CcreAtlasProfile, CcreQueryState, CcreTrackParser
from .errors import ValidationError
from .models import ReferenceContext
from .regulatory_atlas_contracts import (
    RegulatoryAtlasContractRegistry,
    default_regulatory_atlas_contracts,
)
from .regulatory_atlas_public_data import (
    REGULATORY_ATLAS_CONTEXT_KEY,
    RegulatoryAtlasFixture,
    RegulatoryAtlasOperation,
    RegulatoryAtlasRecord,
    RegulatoryAtlasRole,
    build_regulatory_atlas_catalog,
    default_regulatory_atlas_fixture,
    load_regulatory_atlas_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasCheck:
    """One observable evaluation assertion."""

    check_id: str
    record_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasExecutionReceipt:
    """Sanitized parse or query outcome retaining bounded dimensions."""

    record_id: str
    capability_id: str
    operation: RegulatoryAtlasOperation
    role: RegulatoryAtlasRole
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
            raise ValidationError("regulatory receipt counts cannot be negative")

    @property
    def accepted(self) -> bool:
        return self.adapter_state == self.expected_state and not set(
            self.expected_issue_codes
        ) - set(self.observed_issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasEvaluationReport:
    """Whole-fixture report with one receipt and checks per record."""

    fixture_id: str
    fixture_version: str
    context_key: str
    catalog_address: str
    receipts: tuple[RegulatoryAtlasExecutionReceipt, ...]
    checks: tuple[RegulatoryAtlasCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    @property
    def positive_count(self) -> int:
        return sum(receipt.role is RegulatoryAtlasRole.POSITIVE for receipt in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(receipt.role is RegulatoryAtlasRole.CONTROL for receipt in self.receipts)

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
    return value.value if isinstance(value, (CcreQueryState,)) else str(value)


def _check(check_id: str, record_id: str, passed: bool, detail: str) -> RegulatoryAtlasCheck:
    body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
    return RegulatoryAtlasCheck(check_id, record_id, passed, detail, _address(body))


def _issue_codes(
    batch: Any, result: Any | None = None, extra: tuple[str, ...] = ()
) -> tuple[str, ...]:
    values = list(extra)
    values.extend(issue.code for issue in getattr(batch, "issues", ()))
    values.extend(issue.code for issue in getattr(result, "issues", ()))
    if result is not None:
        values.extend(
            {
                CcreQueryState.OUT_OF_DOMAIN: ("ccre_context_mismatch",),
                CcreQueryState.ABSENT: ("no_compatible_ccre",),
                CcreQueryState.AMBIGUOUS: ("ambiguous_ccre_match",),
            }.get(result.state, ())
        )
    return tuple(dict.fromkeys(values))


def _parse_context(payload: dict[str, Any]) -> ReferenceContext:
    context = payload.get("context")
    if not isinstance(context, dict):
        raise ValidationError("regulatory atlas query requires a context object")
    return ReferenceContext.from_dict(context)


def _execute_record(
    record: RegulatoryAtlasRecord,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    """Execute one parse or profile query through the existing cCRE adapters."""

    payload = record.payload
    parser = CcreTrackParser()
    try:
        batch = parser.parse_text(
            payload["input_text"],
            source_id=str(payload["source_id"]),
            profile=str(payload["profile"]),
            input_format=str(payload.get("input_format", "")) or None,
        )
    except ValidationError as exc:
        issue_code = "invalid_ccre_json" if "JSON" in str(exc) else "invalid_ccre_input"
        return (
            "abstained",
            0,
            0,
            (issue_code,),
            {"parse_state": "abstained", "record_count": 0, "issue_codes": (issue_code,)},
        )
    if record.operation is RegulatoryAtlasOperation.CCRE_PARSE:
        state = "partial" if batch.issues else ("supported" if batch.records else "abstained")
        issue_codes = _issue_codes(batch)
        summary = {
            "parse_state": state,
            "record_count": len(batch.records),
            "issue_codes": issue_codes,
            "input_hash": batch.input_hash,
            "record_addresses": tuple(record.raw_hash for record in batch.records),
            "source_id": batch.source_id,
        }
        return state, len(batch.records), len(batch.issues), issue_codes, summary
    try:
        query = payload["query"]
        context = _parse_context(payload)
        if not isinstance(query, dict):
            raise ValidationError("regulatory atlas query must be an object")
        result = CcreAtlasAdapter(
            batch.records,
            profile=CcreAtlasProfile(str(payload["profile"])),
        ).query(
            str(query["chromosome"]),
            int(query["start"]),
            int(query["end"]),
            context,
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return (
            "abstained",
            len(batch.records),
            len(batch.issues),
            ("query_execution_error",),
            {
                "query_state": "abstained",
                "match_count": 0,
                "issue_codes": ("query_execution_error",),
                "error_type": type(exc).__name__,
            },
        )
    issue_codes = _issue_codes(batch, result)
    state = _state_value(result.state)
    summary = {
        "query_state": state,
        "match_count": len(result.matches),
        "reason": result.reason,
        "issue_codes": issue_codes,
        "match_ids": tuple(match.ccre_id for match in result.matches),
        "context_key": context.key,
        "profile": result.profile,
    }
    return state, len(batch.records), len(result.matches), issue_codes, summary


def evaluate_regulatory_atlas_fixture(
    fixture: RegulatoryAtlasFixture | None = None,
    *,
    contracts: RegulatoryAtlasContractRegistry | None = None,
) -> RegulatoryAtlasEvaluationReport:
    """Execute every positive and control record against the cCRE adapters."""

    selected = fixture or default_regulatory_atlas_fixture()
    registry = contracts or default_regulatory_atlas_contracts()
    catalog = build_regulatory_atlas_catalog(selected)
    checks: list[RegulatoryAtlasCheck] = []
    receipts: list[RegulatoryAtlasExecutionReceipt] = []

    def add(check_id: str, record_id: str, passed: bool, detail: str) -> None:
        checks.append(_check(check_id, record_id, passed, detail))

    add(
        "fixture-context",
        "fixture",
        selected.context_key == REGULATORY_ATLAS_CONTEXT_KEY,
        "fixture uses exact regulatory atlas context",
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
                {"error_type": type(exc).__name__},
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
        role_ok = (record.role is RegulatoryAtlasRole.POSITIVE and state == "supported") or (
            record.role is RegulatoryAtlasRole.CONTROL and state != "supported"
        )
        add(role_check, record.record_id, role_ok, "positive and control roles remain distinct")
        check_ids.append(role_check)
        summary_check = f"{record.record_id}:summary"
        summary_ok = all(key in summary for key in ("issue_codes",))
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
        receipt = RegulatoryAtlasExecutionReceipt(
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
        sum(item.role is RegulatoryAtlasRole.POSITIVE for item in receipts) == 4,
        "four positives execute",
    )
    add(
        "control-count",
        "fixture",
        sum(item.role is RegulatoryAtlasRole.CONTROL for item in receipts) == 12,
        "twelve controls execute",
    )
    add(
        "operation-coverage",
        "fixture",
        {item.operation for item in receipts} == set(RegulatoryAtlasOperation),
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
    return RegulatoryAtlasEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        catalog.content_address,
        tuple(receipts),
        tuple(checks),
        _address(body),
    )


def evaluate_regulatory_atlas_fixture_file(path: str | Path) -> RegulatoryAtlasEvaluationReport:
    """Evaluate a fixture descriptor loaded from disk."""

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return evaluate_regulatory_atlas_fixture(load_regulatory_atlas_fixture(payload))


__all__ = [
    "RegulatoryAtlasCheck",
    "RegulatoryAtlasEvaluationReport",
    "RegulatoryAtlasExecutionReceipt",
    "evaluate_regulatory_atlas_fixture",
    "evaluate_regulatory_atlas_fixture_file",
]
