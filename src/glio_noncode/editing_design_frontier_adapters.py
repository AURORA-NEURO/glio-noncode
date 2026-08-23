"""Explicit schema-gated adapters for editing-design operations."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .serialization import content_hash, jsonable
from .editing_design_frontier_contracts import EditingDesignOperation, EditingDesignOperationResult, EditingDesignState
from .editing_design_frontier_operations import run_editing_design_operation
from .editing_design_frontier_schema import EditingDesignSchema, default_editing_design_frontier_schema, validate_editing_design_schema

@dataclass(frozen=True, slots=True)
class EditingDesignAdapter:
    operation: EditingDesignOperation
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class EditingDesignAdapterRegistry:
    adapters: tuple[EditingDesignAdapter, ...]
    schema: EditingDesignSchema
    content_address: str
    def get(self, operation: EditingDesignOperation) -> EditingDesignAdapter: return next(item for item in self.adapters if item.operation == operation)
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_editing_design_adapters(schema: EditingDesignSchema | None = None) -> EditingDesignAdapterRegistry:
    schema = schema or default_editing_design_frontier_schema(); adapters = tuple(EditingDesignAdapter(operation, schema.required_fields[operation.value], schema.output_fields[operation.value], content_hash({"operation": operation, "inputs": schema.required_fields[operation.value]})) for operation in EditingDesignOperation); body = {"adapters": adapters, "schema": schema}; return EditingDesignAdapterRegistry(adapters, schema, content_hash(body))

def execute_editing_design_adapter(registry: EditingDesignAdapterRegistry, operation: EditingDesignOperation, payload: Mapping[str, Any]) -> EditingDesignOperationResult:
    errors = validate_editing_design_schema(payload, operation, registry.schema)
    if errors:
        body = {"operation": operation, "state": EditingDesignState.REJECTED, "issue_codes": ("schema_invalid",), "output": {"schema_errors": errors}}
        return EditingDesignOperationResult(**body, content_address=content_hash(body))
    return run_editing_design_operation(operation, payload)

__all__ = ["EditingDesignAdapter", "EditingDesignAdapterRegistry", "build_editing_design_adapters", "execute_editing_design_adapter"]
