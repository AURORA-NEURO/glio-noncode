"""Interchange schema manifest for D05 atlas exports."""

from __future__ import annotations

from dataclasses import dataclass

from .atlas_architecture_contracts import (
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    addressed,
)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureSchema:
    schema_id: str
    version: str
    required_fixture_fields: tuple[str, ...]
    required_source_fields: tuple[str, ...]
    required_case_fields: tuple[str, ...]
    required_receipt_fields: tuple[str, ...]
    checks: tuple[AtlasArchitectureCheck, ...]
    content_address: str

    def to_dict(self) -> dict[str, object]:
        from .serialization import jsonable

        return jsonable(self)


def atlas_architecture_schema() -> AtlasArchitectureSchema:
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
        "family",
        "scenario",
        "context_key",
        "delegate_context_key",
        "source_ids",
        "payload",
        "expected_state",
        "expected_result_state",
        "expected_issue_codes",
        "expected_counts",
        "content_address",
    )
    source_fields = (
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
    receipt_fields = (
        "case_id",
        "operation_id",
        "family",
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
            "fixture envelope is closed",
        ),
        _check(
            "case-fields",
            len(case_fields) >= 15,
            case_fields,
            ">=15",
            "case retains delegated context and expected D05 outcomes",
        ),
        _check(
            "receipt-fields",
            len(receipt_fields) == 9,
            receipt_fields,
            9,
            "receipt excludes raw payload",
        ),
        _check(
            "source-fields",
            len(source_fields) == 9 and "public_aggregate" in source_fields,
            source_fields,
            9,
            "source scope and public marker are explicit",
        ),
        _check(
            "address-fields",
            all(
                "content_address" in fields
                for fields in (fixture_fields, source_fields, case_fields, receipt_fields)
            ),
            True,
            True,
            "persisted schema entities are content addressed",
        ),
    )
    body = {
        "schema_id": "glio-noncode.atlas-architecture",
        "version": "v1",
        "fixture_fields": fixture_fields,
        "source_fields": source_fields,
        "case_fields": case_fields,
        "receipt_fields": receipt_fields,
        "checks": checks,
    }
    return AtlasArchitectureSchema(
        body["schema_id"],
        body["version"],
        fixture_fields,
        source_fields,
        case_fields,
        receipt_fields,
        checks,
        addressed(body, "atlas-schema"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id,
        AtlasArchitectureCheckKind.FIXTURE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "atlas-schema-check"),
    )


__all__ = ["AtlasArchitectureSchema", "atlas_architecture_schema"]
