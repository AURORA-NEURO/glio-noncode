"""Closed schema manifest for module-fabric public projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .module_fabric_contracts import MODULE_FABRIC_BOUNDARY, MODULE_FABRIC_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FabricField:
    name: str
    section: str
    value_type: str
    required: bool
    public: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricSchema:
    schema_id: str
    version: str
    boundary: str
    fields: tuple[FabricField, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_module_fabric_schema() -> FabricSchema:
    fields = (
        FabricField("fixture_id", "fixture", "string", True, True, "stable public fixture identity"),
        FabricField("fixture_version", "fixture", "string", True, True, "contract version"),
        FabricField("context_key", "fixture", "string", True, True, "exact context boundary"),
        FabricField("evidence_boundary", "fixture", "string", True, True, "public aggregate boundary"),
        FabricField("source_id", "sources", "string", True, True, "source receipt identity"),
        FabricField("uri", "sources", "https_uri", True, True, "public source URI"),
        FabricField("domain_id", "record", "enum:D01-D16", True, True, "owning product domain"),
        FabricField("capability_id", "record", "capability_id", True, True, "owning capability"),
        FabricField("role", "record", "enum:positive/control", True, True, "positive or control role"),
        FabricField("expected_state", "record", "enum", True, True, "declared scenario state"),
        FabricField("observed_state", "execution", "enum", True, True, "observed reference state"),
        FabricField("issue_codes", "execution", "array:string", True, True, "bounded issue vocabulary"),
        FabricField("implementation_reference_count", "execution", "integer", True, True, "count only, no source object"),
        FabricField("test_reference_count", "execution", "integer", True, True, "count only, no source object"),
        FabricField("content_address", "integrity", "sha256", True, True, "immutable receipt address"),
        FabricField("payload", "raw", "object", False, False, "never emitted by public projections"),
    )
    body = {"schema_id": "module-fabric-public-projection", "version": MODULE_FABRIC_VERSION, "boundary": MODULE_FABRIC_BOUNDARY, "fields": fields}
    return FabricSchema(**body, content_address=content_hash(body, prefix="module-fabric-schema"))


def validate_module_fabric_schema(schema: FabricSchema | None = None) -> tuple[str, ...]:
    value = schema or default_module_fabric_schema()
    issues: list[str] = []
    names = tuple(item.name for item in value.fields)
    if len(names) != len(set(names)):
        issues.append("duplicate_field")
    if any(not item.name or not item.section or not item.value_type for item in value.fields):
        issues.append("incomplete_field")
    if any(item.name == "payload" and item.public for item in value.fields):
        issues.append("raw_payload_public")
    if value.boundary != MODULE_FABRIC_BOUNDARY:
        issues.append("boundary_mismatch")
    return tuple(issues)


__all__ = ["FabricField", "FabricSchema", "default_module_fabric_schema", "validate_module_fabric_schema"]
