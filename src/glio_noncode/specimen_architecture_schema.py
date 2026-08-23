"""Schema declarations and closure checks for D03 architecture exports."""

from __future__ import annotations

from dataclasses import dataclass

from .specimen_architecture_contracts import (
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    addressed,
)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureSchema:
    schema_id: str
    version: str
    required_fixture_fields: tuple[str, ...]
    required_case_fields: tuple[str, ...]
    required_receipt_fields: tuple[str, ...]
    checks: tuple[SpecimenArchitectureCheck, ...]
    content_address: str


def specimen_architecture_schema() -> SpecimenArchitectureSchema:
    """Return the closed interchange schema used by fixture and receipt exports."""

    fixture_fields = (
        "fixture_id",
        "version",
        "boundary",
        "context_key",
        "sources",
        "operations",
        "cases",
        "content_address",
    )
    case_fields = (
        "case_id",
        "operation_id",
        "capability_id",
        "operation",
        "scenario",
        "context_key",
        "source_ids",
        "payload",
        "expected_state",
        "expected_result_state",
        "content_address",
    )
    receipt_fields = (
        "case_id",
        "operation_id",
        "observed_state",
        "observed_result_state",
        "observed_issue_codes",
        "observed_counts",
        "output_address",
        "content_address",
    )
    checks = (
        _check(
            "fixture-fields",
            len(fixture_fields) == 8,
            fixture_fields,
            8,
            "fixture interchange fields are declared",
        ),
        _check(
            "case-fields", len(case_fields) >= 10, case_fields, ">=10", "case contract is explicit"
        ),
        _check(
            "receipt-fields",
            len(receipt_fields) == 8,
            receipt_fields,
            8,
            "receipt never carries raw payload",
        ),
    )
    body = {
        "schema_id": "glio-noncode.specimen-architecture",
        "version": "v1",
        "fixture_fields": fixture_fields,
        "case_fields": case_fields,
        "receipt_fields": receipt_fields,
        "checks": checks,
    }
    return SpecimenArchitectureSchema(
        body["schema_id"],
        body["version"],
        fixture_fields,
        case_fields,
        receipt_fields,
        checks,
        addressed(body, "specimen-schema"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SpecimenArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SpecimenArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id,
        SpecimenArchitectureCheckKind.FIXTURE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "specimen-schema-check"),
    )


__all__ = ["SpecimenArchitectureSchema", "specimen_architecture_schema"]
