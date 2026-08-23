"""Input and output schema inventory for platform frontier operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .platform_frontier_contracts import PlatformFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierFieldSpec:
    name: str
    type_name: str
    required: bool
    sensitive: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierSchema:
    schema_id: str
    version: str
    operation_fields: dict[str, tuple[PlatformFrontierFieldSpec, ...]]
    forbidden_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _field(name: str, type_name: str, required: bool = True, sensitive: bool = False, description: str = "") -> PlatformFrontierFieldSpec:
    return PlatformFrontierFieldSpec(name, type_name, required, sensitive, description or name)


def default_platform_frontier_schema() -> PlatformFrontierSchema:
    fields = {
        PlatformFrontierOperation.MISSION_PLANNER.value: (_field("mission_id", "string"), _field("requested_roles", "array"), _field("claim_ceiling", "enum")),
        PlatformFrontierOperation.WORKFLOW_COMPILER.value: (_field("workflow_id", "string"), _field("steps", "array")),
        PlatformFrontierOperation.TYPED_TOOL_REGISTRY.value: (_field("tool_id", "string"), _field("expected_input_contract", "string")),
        PlatformFrontierOperation.EXECUTION_SANDBOX.value: (_field("request_id", "string"), _field("role_id", "string"), _field("tool_id", "string"), _field("input_payload", "object")),
    }
    forbidden = ("clinical_recommendation", "treatment_eligibility", "diagnostic_label", "direct_identifier_value")
    body = {"schema_id": "platform-frontier", "version": "1", "operation_fields": fields, "forbidden_fields": forbidden, "accepted": len(fields) == 4}
    return PlatformFrontierSchema(**body, content_address=content_hash(body))


def validate_platform_frontier_schema(schema: PlatformFrontierSchema) -> tuple[str, ...]:
    issues = []
    if set(schema.operation_fields) != {item.value for item in PlatformFrontierOperation}:
        issues.append("operation_coverage")
    for operation, fields in schema.operation_fields.items():
        names = [item.name for item in fields]
        if len(names) != len(set(names)):
            issues.append(f"duplicate_field:{operation}")
    if not schema.forbidden_fields:
        issues.append("forbidden_field_boundary_missing")
    if any(item.sensitive for fields in schema.operation_fields.values() for item in fields):
        issues.append("sensitive_schema_field")
    return tuple(issues)


__all__ = ["PlatformFrontierFieldSpec", "PlatformFrontierSchema", "default_platform_frontier_schema", "validate_platform_frontier_schema"]
