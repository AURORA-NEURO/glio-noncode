"""Interchange schema manifest for D04 reference architecture exports."""

from __future__ import annotations

from dataclasses import dataclass

from .reference_architecture_contracts import (
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    addressed,
)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureSchema:
    schema_id: str
    version: str
    required_fixture_fields: tuple[str, ...]
    required_case_fields: tuple[str, ...]
    required_receipt_fields: tuple[str, ...]
    checks: tuple[ReferenceArchitectureCheck, ...]
    content_address: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "version": self.version,
            "required_fixture_fields": self.required_fixture_fields,
            "required_case_fields": self.required_case_fields,
            "required_receipt_fields": self.required_receipt_fields,
            "checks": self.checks,
            "content_address": self.content_address,
        }


def reference_architecture_schema() -> ReferenceArchitectureSchema:
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
        "expected_issue_codes",
        "expected_counts",
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
            "fixture fields are closed",
        ),
        _check(
            "case-fields",
            len(case_fields) >= 12,
            case_fields,
            ">=12",
            "case contract retains expected outcomes",
        ),
        _check(
            "receipt-fields",
            len(receipt_fields) == 8,
            receipt_fields,
            8,
            "receipt excludes raw payload",
        ),
    )
    body = {
        "schema_id": "glio-noncode.reference-architecture",
        "version": "v1",
        "fixture_fields": fixture_fields,
        "case_fields": case_fields,
        "receipt_fields": receipt_fields,
        "checks": checks,
    }
    return ReferenceArchitectureSchema(
        body["schema_id"],
        body["version"],
        fixture_fields,
        case_fields,
        receipt_fields,
        checks,
        addressed(body, "reference-schema"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> ReferenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": ReferenceArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceArchitectureCheck(
        check_id,
        ReferenceArchitectureCheckKind.FIXTURE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "reference-schema-check"),
    )


__all__ = ["ReferenceArchitectureSchema", "reference_architecture_schema"]
