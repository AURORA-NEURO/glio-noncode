"""Operation adapter registry with explicit dispatch and schema receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseOperation
from .validation_release_frontier_operations import run_validation_release_operation
from .validation_release_frontier_schema import ValidationReleaseSchema, default_validation_release_frontier_schema, validate_validation_release_schema


@dataclass(frozen=True, slots=True)
class ValidationReleaseAdapter:
    operation: ValidationReleaseOperation
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseAdapterRegistry:
    adapters: tuple[ValidationReleaseAdapter, ...]
    schema: ValidationReleaseSchema
    content_address: str

    def get(self, operation: ValidationReleaseOperation) -> ValidationReleaseAdapter:
        return next(item for item in self.adapters if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_adapters(schema: ValidationReleaseSchema | None = None) -> ValidationReleaseAdapterRegistry:
    schema = schema or default_validation_release_frontier_schema()
    adapters = tuple(ValidationReleaseAdapter(operation, schema.required_fields[operation.value], schema.output_fields[operation.value], content_hash({"operation": operation, "input_fields": schema.required_fields[operation.value]})) for operation in ValidationReleaseOperation)
    body = {"adapters": adapters, "schema": schema}
    return ValidationReleaseAdapterRegistry(adapters, schema, content_hash(body))


def execute_validation_release_adapter(registry: ValidationReleaseAdapterRegistry, operation: ValidationReleaseOperation, payload: Mapping[str, Any]):
    errors = validate_validation_release_schema(payload, operation, registry.schema)
    if errors:
        from .validation_release_frontier_contracts import ValidationReleaseOperationResult, ValidationReleaseState
        body = {"operation": operation, "state": ValidationReleaseState.REJECTED, "issue_codes": ("schema_invalid",), "output": {"schema_errors": errors}}
        return ValidationReleaseOperationResult(**body, content_address=content_hash(body))
    return run_validation_release_operation(operation, payload)


__all__ = ["ValidationReleaseAdapter", "ValidationReleaseAdapterRegistry", "build_validation_release_adapters", "execute_validation_release_adapter"]
