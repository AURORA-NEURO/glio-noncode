"""Explicit adapters that enforce the planning schema before execution."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .serialization import content_hash, jsonable
from .validation_design_frontier_contracts import ValidationDesignOperation, ValidationDesignOperationResult, ValidationDesignState
from .validation_design_frontier_operations import run_validation_design_operation
from .validation_design_frontier_schema import ValidationDesignSchema, default_validation_design_frontier_schema, validate_validation_design_schema

@dataclass(frozen=True, slots=True)
class ValidationDesignAdapter:
    operation: ValidationDesignOperation
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class ValidationDesignAdapterRegistry:
    adapters: tuple[ValidationDesignAdapter, ...]
    schema: ValidationDesignSchema
    content_address: str
    def get(self, operation: ValidationDesignOperation) -> ValidationDesignAdapter: return next(item for item in self.adapters if item.operation == operation)
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_adapters(schema: ValidationDesignSchema | None = None) -> ValidationDesignAdapterRegistry:
    schema = schema or default_validation_design_frontier_schema()
    adapters = tuple(ValidationDesignAdapter(operation, schema.required_fields[operation.value], schema.output_fields[operation.value], content_hash({"operation": operation, "inputs": schema.required_fields[operation.value]})) for operation in ValidationDesignOperation)
    body = {"adapters": adapters, "schema": schema}
    return ValidationDesignAdapterRegistry(adapters, schema, content_hash(body))

def execute_validation_design_adapter(registry: ValidationDesignAdapterRegistry, operation: ValidationDesignOperation, payload: Mapping[str, Any]) -> ValidationDesignOperationResult:
    errors = validate_validation_design_schema(payload, operation, registry.schema)
    if errors:
        body = {"operation": operation, "state": ValidationDesignState.REJECTED, "issue_codes": ("schema_invalid",), "output": {"schema_errors": errors}}
        return ValidationDesignOperationResult(**body, content_address=content_hash(body))
    return run_validation_design_operation(operation, payload)

__all__ = ["ValidationDesignAdapter", "ValidationDesignAdapterRegistry", "build_validation_design_adapters", "execute_validation_design_adapter"]
