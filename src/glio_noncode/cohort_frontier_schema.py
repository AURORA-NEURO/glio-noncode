"""Schema manifest for Domain 12 cohort convergence operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_contracts import default_cohort_frontier_contracts
from .cohort_frontier_public_data import CohortFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierFieldSpec:
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
class CohortFrontierOperationSchema:
    operation: CohortFrontierOperation
    input_fields: tuple[CohortFrontierFieldSpec, ...]
    output_fields: tuple[CohortFrontierFieldSpec, ...]
    issue_codes: tuple[str, ...]
    content_address: str

    def field_names(self) -> tuple[str, ...]:
        return tuple(item.field_name for item in self.input_fields + self.output_fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierSchemaManifest:
    schema_id: str
    version: str
    operations: tuple[CohortFrontierOperationSchema, ...]
    invariant_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.schema_id, "schema_id")
        require_non_empty(self.version, "version")
        if {item.operation for item in self.operations} != set(CohortFrontierOperation):
            raise ValueError("cohort schema must cover operations")

    def by_operation(self, operation: CohortFrontierOperation) -> CohortFrontierOperationSchema:
        return next(item for item in self.operations if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _field(name: str, value_type: str, required: bool, nullable: bool, role: str, validation: str) -> CohortFrontierFieldSpec:
    body = {"field_name": name, "value_type": value_type, "required": required, "nullable": nullable, "semantic_role": role, "validation": validation}
    return CohortFrontierFieldSpec(**body, content_address=content_hash(body))


def default_cohort_frontier_schema() -> CohortFrontierSchemaManifest:
    common_in = (_field("input_records", "array<object>", True, False, "operation input", "array may be empty only for controls"), _field("context_key", "string", True, False, "exact cohort scope", "context retained"))
    common_out = (_field("content_address", "string", True, False, "integrity receipt", "sha256 address"), _field("state", "enum", True, False, "bounded outcome", "supported, review, invalid, published"))
    contracts = default_cohort_frontier_contracts()
    operations = []
    for operation in CohortFrontierOperation:
        contract = contracts.by_operation(operation)
        extras = tuple(_field(field, "number|string|array", True, False, "operation parameter", "contract validation") for field in contract.required_payload_fields if field != "input_records")
        body = {"operation": operation, "input_fields": common_in + extras, "output_fields": common_out, "issue_codes": contract.issue_vocabulary}
        operations.append(CohortFrontierOperationSchema(**body, content_address=content_hash(body)))
    body = {"schema_id": "cohort-frontier-schema", "version": "2026.08.d12.v1", "operations": tuple(operations), "invariant_ids": ("context-preserved", "control-complete", "source-addressed", "privacy-floor-visible", "excluded-uses-retained")}
    return CohortFrontierSchemaManifest(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierFieldSpec", "CohortFrontierOperationSchema", "CohortFrontierSchemaManifest", "default_cohort_frontier_schema"]
