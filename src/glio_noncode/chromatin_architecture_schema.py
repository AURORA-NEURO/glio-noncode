"""Interchange schema and structural checks for the D07 aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import (
    CHROMATIN_ARCHITECTURE_CASE_COUNT,
    CHROMATIN_ARCHITECTURE_CASES_PER_OPERATION,
    CHROMATIN_ARCHITECTURE_FAMILY_COUNT,
    CHROMATIN_ARCHITECTURE_SOURCE_COUNT,
    CHROMATIN_ARCHITECTURE_VERSION,
    ChromatinArchitectureCheck,
    ChromatinArchitectureCheckKind,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureSchemaField:
    name: str
    value_type: str
    required: bool
    description: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureSchema:
    schema_id: str
    version: str
    fields: tuple[ChromatinArchitectureSchemaField, ...]
    operation_contracts: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureSchemaReport:
    fixture_id: str
    schema: ChromatinArchitectureSchema
    checks: tuple[ChromatinArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


_FIELD_SPECS = (
    ("fixture_id", "string", True, "stable aggregate fixture identity"),
    ("version", "string", True, "pinned contract version"),
    ("boundary", "string", True, "public aggregate evidence boundary"),
    ("context_key", "string", True, "exact reference and biological context"),
    ("source_id", "string", True, "prefixed public source receipt ID"),
    ("source_family", "enum", True, "one of four D07 family tranches"),
    ("source_uri", "uri", True, "HTTPS source locator"),
    ("source_version", "string", True, "release or version receipt"),
    ("source_scope", "enum", True, "public aggregate only"),
    ("source_public_aggregate", "boolean", True, "explicit public aggregate marker"),
    ("operation_id", "string", True, "D07 operation identity"),
    ("capability_id", "string", True, "blueprint capability identity"),
    ("operation_family", "enum", True, "family delegation boundary"),
    ("operation_plane", "enum", True, "evidence plane"),
    ("input_contract", "string", True, "operation input contract"),
    ("output_contract", "string", True, "operation receipt contract"),
    ("scenario", "enum", True, "positive or explicit control scenario"),
    ("case_context", "string", True, "case-level context key"),
    ("delegate_context", "string", True, "context retained at delegation boundary"),
    ("case_sources", "array[string]", True, "source joins for the case"),
    ("expected_state", "enum", True, "aggregate state expectation"),
    ("expected_result_state", "string", True, "family or release result expectation"),
    ("expected_issue_codes", "array[string]", True, "issue floor for the case"),
    ("expected_counts", "object", True, "bounded evidence count expectation"),
    ("observed_state", "enum", True, "runtime aggregate state"),
    ("observed_result_state", "string", True, "runtime family result state"),
    ("observed_issue_codes", "array[string]", True, "runtime issue receipt"),
    ("observed_counts", "object", True, "runtime evidence counts"),
    ("summary", "object", True, "sanitized review-safe operation summary"),
    ("output_address", "sha256", True, "execution output address"),
    ("receipt_address", "sha256", True, "case receipt address"),
    ("lineage_address", "sha256", True, "source-to-receipt lineage address"),
    ("release_state", "enum", True, "release boundary state"),
)


def chromatin_architecture_schema() -> ChromatinArchitectureSchema:
    fields = tuple(
        ChromatinArchitectureSchemaField(
            name=name,
            value_type=value_type,
            required=required,
            description=description,
            content_address=addressed(
                {
                    "name": name,
                    "value_type": value_type,
                    "required": required,
                    "description": description,
                },
                "chromatin-schema-field",
            ),
        )
        for name, value_type, required, description in _FIELD_SPECS
    )
    body = {
        "schema_id": "glio-noncode.d07.chromatin-architecture",
        "version": CHROMATIN_ARCHITECTURE_VERSION,
        "fields": fields,
        "operation_contracts": tuple(f"GNC-D07-C{index:02d}" for index in range(1, 17)),
    }
    return ChromatinArchitectureSchema(**body, content_address=addressed(body, "chromatin-schema"))


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> ChromatinArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": ChromatinArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ChromatinArchitectureCheck(
        **body, content_address=addressed(body, "chromatin-schema-check")
    )


def validate_chromatin_architecture_schema(
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
) -> ChromatinArchitectureSchemaReport:
    schema = chromatin_architecture_schema()
    checks = (
        _check(
            "schema-version",
            schema.version == CHROMATIN_ARCHITECTURE_VERSION,
            schema.version,
            CHROMATIN_ARCHITECTURE_VERSION,
            "schema version matches fixture",
        ),
        _check(
            "field-cardinality",
            len(schema.fields) == 33,
            len(schema.fields),
            33,
            "all aggregate fields are declared",
        ),
        _check(
            "operation-contracts",
            len(schema.operation_contracts) == 16,
            len(schema.operation_contracts),
            16,
            "every capability has an interchange contract",
        ),
        _check(
            "fixture-contract",
            fixture.version == schema.version,
            fixture.version,
            schema.version,
            "fixture binds to schema",
        ),
        _check(
            "receipt-cardinality",
            len(evaluation.receipts) == 64,
            len(evaluation.receipts),
            64,
            "all case receipts are schema-shaped",
        ),
        _check(
            "receipt-addresses",
            all(item.content_address.startswith("sha256:") for item in evaluation.receipts),
            sum(item.content_address.startswith("sha256:") for item in evaluation.receipts),
            64,
            "receipt addresses are present",
        ),
        _check(
            "summary-sanitized",
            all(
                not any(key in jsonable(item) for key in ("payload", "input_text", "track_text"))
                for item in evaluation.executions
            ),
            True,
            "summaries exclude raw input",
            "review-safe summaries are sanitized",
        ),
        _check(
            "source-cardinality",
            len(fixture.sources) == CHROMATIN_ARCHITECTURE_SOURCE_COUNT,
            len(fixture.sources),
            CHROMATIN_ARCHITECTURE_SOURCE_COUNT,
            "source registry cardinality is fixed",
        ),
        _check(
            "source-public-markers",
            all(item.public_aggregate for item in fixture.sources),
            sum(item.public_aggregate for item in fixture.sources),
            CHROMATIN_ARCHITECTURE_SOURCE_COUNT,
            "all sources explicitly declare public aggregate scope",
        ),
        _check(
            "operation-case-balance",
            all(
                sum(item.operation_id == operation.operation_id for item in fixture.cases)
                == CHROMATIN_ARCHITECTURE_CASES_PER_OPERATION
                for operation in fixture.operations
            ),
            len(fixture.cases),
            CHROMATIN_ARCHITECTURE_CASE_COUNT,
            "every operation has four scenario cases",
        ),
        _check(
            "family-cardinality",
            len({item.family for item in fixture.operations})
            == CHROMATIN_ARCHITECTURE_FAMILY_COUNT,
            len({item.family for item in fixture.operations}),
            CHROMATIN_ARCHITECTURE_FAMILY_COUNT,
            "all four D07 family tranches are represented",
        ),
        _check(
            "delegated-contexts",
            all(item.delegate_context_key for item in fixture.cases),
            sum(bool(item.delegate_context_key) for item in fixture.cases),
            CHROMATIN_ARCHITECTURE_CASE_COUNT,
            "every case retains a delegated context key",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "schema": schema, "checks": checks}
    return ChromatinArchitectureSchemaReport(
        fixture.fixture_id,
        schema,
        checks,
        all(item.passed for item in checks),
        addressed(body, "chromatin-schema-report"),
    )


__all__ = [
    "ChromatinArchitectureSchema",
    "ChromatinArchitectureSchemaField",
    "ChromatinArchitectureSchemaReport",
    "chromatin_architecture_schema",
    "validate_chromatin_architecture_schema",
]
