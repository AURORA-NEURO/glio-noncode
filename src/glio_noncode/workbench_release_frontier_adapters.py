"""Explicit adapter registry for workbench-release operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable
from .workbench_release_frontier_contracts import WorkbenchReleaseOperation, WorkbenchReleaseOperationResult, WorkbenchReleaseState
from .workbench_release_frontier_operations import run_workbench_release_operation
from .workbench_release_frontier_schema import WorkbenchReleaseSchema, default_workbench_release_frontier_schema, validate_workbench_release_schema


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseAdapter:
    operation: WorkbenchReleaseOperation
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseAdapterRegistry:
    adapters: tuple[WorkbenchReleaseAdapter, ...]
    schema: WorkbenchReleaseSchema
    content_address: str

    def get(self, operation: WorkbenchReleaseOperation) -> WorkbenchReleaseAdapter:
        return next(item for item in self.adapters if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_workbench_release_adapters(schema: WorkbenchReleaseSchema | None = None) -> WorkbenchReleaseAdapterRegistry:
    schema = schema or default_workbench_release_frontier_schema()
    adapters = tuple(WorkbenchReleaseAdapter(operation, schema.required_fields[operation.value], schema.output_fields[operation.value], content_hash({"operation": operation, "input_fields": schema.required_fields[operation.value]})) for operation in WorkbenchReleaseOperation)
    body = {"adapters": adapters, "schema": schema}
    return WorkbenchReleaseAdapterRegistry(adapters, schema, content_hash(body))


def execute_workbench_release_adapter(registry: WorkbenchReleaseAdapterRegistry, operation: WorkbenchReleaseOperation, payload: Mapping[str, Any]) -> WorkbenchReleaseOperationResult:
    errors = validate_workbench_release_schema(payload, operation, registry.schema)
    if errors:
        body = {"operation": operation, "state": WorkbenchReleaseState.REJECTED, "issue_codes": ("schema_invalid",), "output": {"schema_errors": errors}}
        return WorkbenchReleaseOperationResult(**body, content_address=content_hash(body))
    return run_workbench_release_operation(operation, payload)


__all__ = ["WorkbenchReleaseAdapter", "WorkbenchReleaseAdapterRegistry", "build_workbench_release_adapters", "execute_workbench_release_adapter"]
