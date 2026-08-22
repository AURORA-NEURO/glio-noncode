"""Typed surface schema for the Domain 14 lifecycle frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleFieldSpec:
    name: str
    value_type: str
    required: bool
    nullable: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOperationSchema:
    operation: EvidenceLifecycleOperation
    input_fields: tuple[EvidenceLifecycleFieldSpec, ...]
    output_fields: tuple[EvidenceLifecycleFieldSpec, ...]
    content_address: str

    def field_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.input_fields + self.output_fields)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleSchemaManifest:
    schema_id: str
    version: str
    operations: tuple[EvidenceLifecycleOperationSchema, ...]
    content_address: str

    def by_operation(self, operation: EvidenceLifecycleOperation) -> EvidenceLifecycleOperationSchema:
        return next(item for item in self.operations if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _field(name: str, value_type: str, required: bool, detail: str, *, nullable: bool = False) -> EvidenceLifecycleFieldSpec:
    body = {"name": name, "value_type": value_type, "required": required, "nullable": nullable, "detail": detail}
    return EvidenceLifecycleFieldSpec(**body, content_address=content_hash(body))


def default_evidence_lifecycle_schema() -> EvidenceLifecycleSchemaManifest:
    shared_in = (_field("record_id", "string", True, "fixture record identity"), _field("context_key", "string", True, "exact graph context"), _field("source_ids", "array[string]", True, "source receipt bindings"), _field("payload", "object", True, "operation payload"))
    rows = tuple(EvidenceLifecycleOperationSchema(operation, shared_in + ((_field("text", "string", operation is EvidenceLifecycleOperation.CITATION_RESOLUTION, "citation input text"),),)[0] if operation is EvidenceLifecycleOperation.CITATION_RESOLUTION else shared_in, (_field("state", "string", True, "declared lifecycle state"), _field("content_address", "string", True, "content address")), content_hash({"operation": operation, "input_fields": shared_in, "output": ("state", "content_address")})) for operation in EvidenceLifecycleOperation)
    body = {"schema_id": "evidence-lifecycle-frontier-schema", "version": "2026.08.d14.v1", "operations": rows}
    return EvidenceLifecycleSchemaManifest(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleFieldSpec", "EvidenceLifecycleOperationSchema", "EvidenceLifecycleSchemaManifest", "default_evidence_lifecycle_schema"]
