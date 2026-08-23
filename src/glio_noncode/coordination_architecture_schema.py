"""Projection schema manifest for the coordination architecture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_contracts import addressed


@dataclass(frozen=True, slots=True)
class CoordinationSchemaField:
    name: str
    type_name: str
    required: bool
    public: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type_name": self.type_name,
            "required": self.required,
            "public": self.public,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class CoordinationSchemaManifest:
    schema_id: str
    version: str
    fields: tuple[CoordinationSchemaField, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "version": self.version,
            "fields": tuple(item.to_dict() for item in self.fields),
            "content_address": self.content_address,
        }


def default_coordination_schema() -> CoordinationSchemaManifest:
    fields = tuple(
        CoordinationSchemaField(name, type_name, True, True, detail)
        for name, type_name, detail in (
            ("run_id", "string", "stable runtime identifier"),
            ("fixture_id", "string", "content-addressed public fixture identifier"),
            ("state", "enum", "accepted or held runtime state"),
            ("stage_count", "integer", "ordered runtime stage count"),
            ("operation_count", "integer", "compiled operation count"),
            ("case_count", "integer", "executed aggregate case count"),
            ("accepted_cases", "integer", "reconciled case count"),
            ("review_queue", "object", "held-control routing summary"),
            ("quality", "object", "named quality check counts"),
            ("content_address", "string", "runtime content address"),
        )
    )
    body = {"schema_id": "coordination-runtime-projection", "version": "1", "fields": fields}
    return CoordinationSchemaManifest(**body, content_address=addressed(body, "coordination-schema"))


def validate_coordination_schema(schema: CoordinationSchemaManifest) -> tuple[str, ...]:
    issues: list[str] = []
    if not schema.fields:
        issues.append("empty_schema")
    if len({item.name for item in schema.fields}) != len(schema.fields):
        issues.append("duplicate_field")
    if any(not item.public or not item.required for item in schema.fields):
        issues.append("closed_public_fields_required")
    return tuple(sorted(set(issues)))


__all__ = ["CoordinationSchemaField", "CoordinationSchemaManifest", "default_coordination_schema", "validate_coordination_schema"]
