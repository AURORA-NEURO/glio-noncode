"""Schema manifest and field-level invariants for the causal frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_contracts import default_causal_frontier_contracts
from .causal_frontier_public_data import CausalFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierFieldSpec:
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
class CausalFrontierOperationSchema:
    operation: CausalFrontierOperation
    input_fields: tuple[CausalFrontierFieldSpec, ...]
    output_fields: tuple[CausalFrontierFieldSpec, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def field_names(self) -> tuple[str, ...]:
        return tuple(item.field_name for item in self.input_fields + self.output_fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierSchemaManifest:
    schema_id: str
    version: str
    operations: tuple[CausalFrontierOperationSchema, ...]
    invariant_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.schema_id, "schema_id")
        require_non_empty(self.version, "version")
        if {item.operation for item in self.operations} != set(CausalFrontierOperation):
            raise ValueError("schema must cover every causal operation")

    def by_operation(self, operation: CausalFrontierOperation) -> CausalFrontierOperationSchema:
        return next(item for item in self.operations if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _field(name: str, value_type: str, required: bool, nullable: bool, role: str, validation: str) -> CausalFrontierFieldSpec:
    body = {"field_name": name, "value_type": value_type, "required": required, "nullable": nullable, "semantic_role": role, "validation": validation}
    return CausalFrontierFieldSpec(**body, content_address=content_hash(body))


def default_causal_frontier_schema() -> CausalFrontierSchemaManifest:
    common_in = (
        _field("input_records", "array<object>", True, False, "operation input", "array may be empty only for negative controls"),
        _field("context_key", "string", True, False, "context identity", "exact context retained through output"),
    )
    common_out = (
        _field("content_address", "string", True, False, "integrity receipt", "sha256 content address"),
        _field("state", "enum", True, False, "bounded outcome", "supported, partial, invalid, or published"),
    )
    issue_map = default_causal_frontier_contracts()
    operations: list[CausalFrontierOperationSchema] = []
    for operation in CausalFrontierOperation:
        contract = issue_map.by_operation(operation)
        extras = tuple(
            _field(field, "number|string|array", field != "minimum_support", False, "operation parameter", "contract-defined validation")
            for field in contract.required_payload_fields
            if field != "input_records"
        )
        body = {
            "operation": operation,
            "input_fields": common_in + extras,
            "output_fields": common_out,
            "issue_codes": contract.issue_vocabulary,
        }
        operations.append(CausalFrontierOperationSchema(**body, content_address=content_hash(body)))
    body = {
        "schema_id": "causal-frontier-evidence-schema",
        "version": "2026.08.d11.v1",
        "operations": tuple(operations),
        "invariant_ids": ("context-preserved", "bounded-scores", "content-addressed", "controls-required", "public-boundary"),
    }
    return CausalFrontierSchemaManifest(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierFieldSpec", "CausalFrontierOperationSchema", "CausalFrontierSchemaManifest", "default_causal_frontier_schema"]
