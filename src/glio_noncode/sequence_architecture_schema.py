"""Interchange schema manifest for D06 fixture and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class SequenceArchitectureSchema:
    version: str
    fixture_fields: tuple[str, ...]
    source_fields: tuple[str, ...]
    operation_fields: tuple[str, ...]
    case_fields: tuple[str, ...]
    receipt_fields: tuple[str, ...]
    checks: tuple[SequenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def sequence_architecture_schema() -> SequenceArchitectureSchema:
    fixture = (
        "fixture_id",
        "version",
        "boundary",
        "context_key",
        "sources",
        "operations",
        "cases",
        "content_address",
    )
    source = (
        "source_id",
        "family",
        "title",
        "uri",
        "version",
        "scope",
        "license",
        "public_aggregate",
        "content_address",
    )
    operation = (
        "operation_id",
        "capability_id",
        "ordinal",
        "operation",
        "family",
        "plane",
        "input_contract",
        "output_contract",
        "dependencies",
        "source_ids",
        "control_policy",
        "content_address",
    )
    case = (
        "case_id",
        "operation_id",
        "capability_id",
        "operation",
        "family",
        "plane",
        "scenario",
        "context_key",
        "delegate_context_key",
        "source_ids",
        "payload",
        "expected_state",
        "expected_result_state",
        "expected_issue_codes",
        "expected_counts",
        "description",
        "content_address",
    )
    receipt = (
        "case_id",
        "operation_id",
        "family",
        "expected_state",
        "observed_state",
        "expected_result_state",
        "observed_result_state",
        "expected_issue_codes",
        "observed_issue_codes",
        "expected_counts",
        "observed_counts",
        "passed",
        "output_address",
        "detail",
        "content_address",
    )
    checks = (
        _check(
            "schema-fixture-fields",
            len(fixture) == 8,
            len(fixture),
            8,
            "fixture interchange fields are stable",
        ),
        _check(
            "schema-case-fields",
            len(case) == 17,
            len(case),
            17,
            "case fields retain payload, context delegation, and expectations",
        ),
        _check(
            "schema-receipt-fields",
            len(receipt) == 15,
            len(receipt),
            15,
            "receipt fields retain expected and observed values",
        ),
        _check(
            "schema-source-public-marker",
            "public_aggregate" in source,
            "public_aggregate" in source,
            True,
            "source scope is explicit in the interchange schema",
        ),
        _check(
            "schema-case-context-delegation",
            "delegate_context_key" in case,
            "delegate_context_key" in case,
            True,
            "case context delegation is explicit in the interchange schema",
        ),
        _check(
            "schema-address-fields",
            all(
                "content_address" in fields
                for fields in (fixture, source, operation, case, receipt)
            ),
            True,
            True,
            "every persisted entity has an address",
        ),
    )
    body = {
        "version": "2026.08.d06-sequence-schema.v1",
        "fixture_fields": fixture,
        "source_fields": source,
        "operation_fields": operation,
        "case_fields": case,
        "receipt_fields": receipt,
        "checks": checks,
    }
    return SequenceArchitectureSchema(
        version=body["version"],
        fixture_fields=fixture,
        source_fields=source,
        operation_fields=operation,
        case_fields=case,
        receipt_fields=receipt,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-schema"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.FIXTURE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-schema-check"),
    )


__all__ = ["SequenceArchitectureSchema", "sequence_architecture_schema"]
