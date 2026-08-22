"""Field schema manifest for Domain 13 planning operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .validation_frontier_contracts import default_validation_frontier_contracts
from .validation_frontier_public_data import ValidationFrontierOperation


@dataclass(frozen=True, slots=True)
class ValidationFrontierFieldSpec:
    field_name: str
    value_type: str
    required: bool
    nullable: bool
    semantic_role: str
    validation: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("field_name", "value_type", "semantic_role", "validation"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierOperationSchema:
    operation: ValidationFrontierOperation
    input_fields: tuple[ValidationFrontierFieldSpec, ...]
    output_fields: tuple[ValidationFrontierFieldSpec, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def field_names(self) -> tuple[str, ...]:
        return tuple(item.field_name for item in self.input_fields + self.output_fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierSchemaManifest:
    schema_id: str
    version: str
    operations: tuple[ValidationFrontierOperationSchema, ...]
    invariant_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.schema_id, "schema_id")
        require_non_empty(self.version, "version")
        if {item.operation for item in self.operations} != set(ValidationFrontierOperation):
            raise ValueError("validation schema must cover operations")

    def by_operation(self, operation: ValidationFrontierOperation) -> ValidationFrontierOperationSchema:
        return next(item for item in self.operations if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _field(name: str, value_type: str, required: bool, nullable: bool, role: str, validation: str) -> ValidationFrontierFieldSpec:
    body = {"field_name": name, "value_type": value_type, "required": required, "nullable": nullable, "semantic_role": role, "validation": validation}
    return ValidationFrontierFieldSpec(**body, content_address=content_hash(body))


def default_validation_frontier_schema() -> ValidationFrontierSchemaManifest:
    common_in = (_field("context_key", "string", True, False, "exact planning scope", "must equal fixture context"),)
    common_out = (_field("state", "enum", True, False, "bounded planning state", "partial, ready_for_review, blocked, abstained, invalid"), _field("content_address", "string", True, False, "integrity receipt", "sha256 address"))
    contracts = default_validation_frontier_contracts()
    operations = []
    for operation in ValidationFrontierOperation:
        contract = contracts.by_operation(operation)
        inputs = common_in + tuple(_field(field, "object|array", True, False, "operation input", "contract validation") for field in contract.required_payload_fields if field != "context_key")
        body = {"operation": operation, "input_fields": inputs, "output_fields": common_out, "issue_codes": contract.issue_vocabulary}
        operations.append(ValidationFrontierOperationSchema(**body, content_address=content_hash(body)))
    body = {"schema_id": "validation-frontier-schema", "version": "2026.08.d13.v1", "operations": tuple(operations), "invariant_ids": ("context-preserved", "positive-control-separated", "source-addressed", "blockers-visible", "limitations-retained")}
    return ValidationFrontierSchemaManifest(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierFieldSpec", "ValidationFrontierOperationSchema", "ValidationFrontierSchemaManifest", "default_validation_frontier_schema"]
