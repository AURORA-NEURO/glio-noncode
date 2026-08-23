"""Typed adapter registry for the four evidence-release operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .evidence_release_frontier_contracts import EvidenceReleaseOperation, EvidenceReleaseOperationResult, EvidenceReleaseState
from .evidence_release_frontier_operations import run_evidence_release_operation
from .evidence_release_frontier_schema import EvidenceReleaseSchema, default_evidence_release_frontier_schema, validate_evidence_release_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseAdapter:
    operation: EvidenceReleaseOperation
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceReleaseAdapterRegistry:
    adapters: tuple[EvidenceReleaseAdapter, ...]
    schema: EvidenceReleaseSchema
    content_address: str

    def get(self, operation: EvidenceReleaseOperation) -> EvidenceReleaseAdapter:
        return next(item for item in self.adapters if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_adapters(schema: EvidenceReleaseSchema | None = None) -> EvidenceReleaseAdapterRegistry:
    schema = schema or default_evidence_release_frontier_schema()
    adapters = tuple(EvidenceReleaseAdapter(operation, schema.required_fields[operation.value], schema.output_fields[operation.value], content_hash({"operation": operation, "input_fields": schema.required_fields[operation.value]})) for operation in EvidenceReleaseOperation)
    body = {"adapters": adapters, "schema": schema}
    return EvidenceReleaseAdapterRegistry(adapters, schema, content_hash(body))


def execute_evidence_release_adapter(registry: EvidenceReleaseAdapterRegistry, operation: EvidenceReleaseOperation, payload: Mapping[str, Any]) -> EvidenceReleaseOperationResult:
    errors = validate_evidence_release_schema(payload, operation, registry.schema)
    if errors:
        body = {"operation": operation, "state": EvidenceReleaseState.REJECTED, "issue_codes": ("schema_invalid",), "output": {"schema_errors": errors}}
        return EvidenceReleaseOperationResult(**body, content_address=content_hash(body))
    return run_evidence_release_operation(operation, payload)


__all__ = ["EvidenceReleaseAdapter", "EvidenceReleaseAdapterRegistry", "build_evidence_release_adapters", "execute_evidence_release_adapter"]
