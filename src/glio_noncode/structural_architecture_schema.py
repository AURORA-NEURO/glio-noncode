"""Field-level schema manifest for D02 architecture exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .structural_architecture_contracts import StructuralArchitectureFixture, addressed


@dataclass(frozen=True, slots=True)
class StructuralArchitectureSchemaField:
    path: str
    value_type: str
    required: bool
    aggregate_safe: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "value_type": self.value_type,
            "required": self.required,
            "aggregate_safe": self.aggregate_safe,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class StructuralArchitectureSchemaReport:
    schema_id: str
    version: str
    fields: tuple[StructuralArchitectureSchemaField, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "version": self.version,
            "fields": [item.to_dict() for item in self.fields],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def default_structural_architecture_schema() -> StructuralArchitectureSchemaReport:
    fields = (
        StructuralArchitectureSchemaField(
            "fixture_id", "string", True, True, "stable fixture identity"
        ),
        StructuralArchitectureSchemaField(
            "context_key", "string", True, True, "six-field assembly and aggregate context"
        ),
        StructuralArchitectureSchemaField(
            "sources[].uri", "https-url", True, True, "public source receipt URI"
        ),
        StructuralArchitectureSchemaField(
            "operations[].capability_id", "string", True, True, "closed capability join"
        ),
        StructuralArchitectureSchemaField(
            "cases[].public_identifier", "string", True, True, "public bounded identifier"
        ),
        StructuralArchitectureSchemaField(
            "cases[].payload", "object", True, True, "bounded mechanics payload"
        ),
        StructuralArchitectureSchemaField(
            "cases[].expected_state", "enum", True, True, "release assertion"
        ),
        StructuralArchitectureSchemaField(
            "cases[].content_address", "sha256", True, True, "case identity address"
        ),
        StructuralArchitectureSchemaField(
            "receipts[].observed_issue_codes",
            "array[string]",
            True,
            True,
            "review-preserving issue codes",
        ),
        StructuralArchitectureSchemaField(
            "release.rollback_key", "sha256", True, True, "recoverable release pointer"
        ),
    )
    body = {
        "schema_id": "structural-architecture",
        "version": "v1",
        "fields": fields,
        "accepted": True,
    }
    return StructuralArchitectureSchemaReport(
        **body, content_address=addressed(body, "structural-schema")
    )


def validate_structural_architecture_schema(
    fixture: StructuralArchitectureFixture,
) -> StructuralArchitectureSchemaReport:
    schema = default_structural_architecture_schema()
    required = {item.path for item in schema.fields if item.required}
    observed = {
        "fixture_id",
        "context_key",
        "sources[].uri",
        "operations[].capability_id",
        "cases[].public_identifier",
        "cases[].payload",
        "cases[].expected_state",
        "cases[].content_address",
    }
    accepted = required.issuperset(observed) and bool(fixture.sources) and bool(fixture.cases)
    body = {
        "schema_id": schema.schema_id,
        "version": schema.version,
        "fields": schema.fields,
        "accepted": accepted,
    }
    return StructuralArchitectureSchemaReport(
        **body, content_address=addressed(body, "structural-schema-validation")
    )


__all__ = [
    "StructuralArchitectureSchemaField",
    "StructuralArchitectureSchemaReport",
    "default_structural_architecture_schema",
    "validate_structural_architecture_schema",
]
