"""Schema manifest for public control frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierFieldSpec:
    name: str
    required: bool
    type_name: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierSchema:
    schema_id: str
    version: str
    common_fields: tuple[ControlFrontierFieldSpec, ...]
    operation_fields: dict[str, tuple[ControlFrontierFieldSpec, ...]]
    content_address: str

    @property
    def field_count(self) -> int:
        return len(self.common_fields) + sum(len(item) for item in self.operation_fields.values())

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"field_count": self.field_count}


def default_control_frontier_schema() -> ControlFrontierSchema:
    common = tuple(ControlFrontierFieldSpec(*item) for item in (
        ("record_id", True, "string", "stable row identity"),
        ("operation", True, "enum", "allowlisted operation"),
        ("role", True, "enum", "positive or control role"),
        ("context_key", True, "string", "exact support context"),
        ("source_ids", True, "array[string]", "public source receipts"),
        ("state", True, "enum", "observed operation state"),
        ("issue_codes", True, "array[string]", "explicit blockers and warnings"),
        ("content_address", True, "sha256", "receipt address"),
    ))
    operation_fields = {operation.value: (ControlFrontierFieldSpec("output", True, "object", "structured operation projection"),) for operation in ControlFrontierOperation}
    body = {"schema_id": "control-frontier-public-receipts", "version": "v1", "common_fields": common, "operation_fields": operation_fields}
    return ControlFrontierSchema(**body, content_address=content_hash(body))


def validate_control_frontier_schema(schema: ControlFrontierSchema) -> tuple[str, ...]:
    """Return missing schema elements instead of raising on review input."""

    required = {item.name for item in schema.common_fields if item.required}
    issues = []
    for name in ("record_id", "operation", "role", "context_key", "source_ids", "state", "issue_codes", "content_address"):
        if name not in required:
            issues.append(f"missing_common_field:{name}")
    for operation in ControlFrontierOperation:
        if operation.value not in schema.operation_fields:
            issues.append(f"missing_operation:{operation.value}")
    return tuple(issues)


__all__ = ["ControlFrontierFieldSpec", "ControlFrontierSchema", "default_control_frontier_schema", "validate_control_frontier_schema"]
