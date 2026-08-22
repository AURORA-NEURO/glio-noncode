"""Input adapter declarations for Domain 14 lifecycle records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleInputAdapter:
    adapter_id: str
    operation: EvidenceLifecycleOperation
    accepted_formats: tuple[str, ...]
    required_fields: tuple[str, ...]
    rejects_patient_scope: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleAdapterReceipt:
    adapter_id: str
    accepted: bool
    normalized_fields: tuple[str, ...]
    rejected_fields: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleAdapterRegistry:
    registry_id: str
    adapters: tuple[EvidenceLifecycleInputAdapter, ...]
    content_address: str

    def by_operation(self, operation: EvidenceLifecycleOperation) -> EvidenceLifecycleInputAdapter:
        return next(item for item in self.adapters if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_evidence_lifecycle_adapters() -> EvidenceLifecycleAdapterRegistry:
    rows = tuple(EvidenceLifecycleInputAdapter(f"d14-{operation.value}", operation, ("json", "mapping", "text"), ("record_id", "context_key", "payload"), True, "") for operation in EvidenceLifecycleOperation)
    rows = tuple(EvidenceLifecycleInputAdapter(item.adapter_id, item.operation, item.accepted_formats, item.required_fields, item.rejects_patient_scope, content_hash({"adapter_id": item.adapter_id, "operation": item.operation, "accepted_formats": item.accepted_formats, "required_fields": item.required_fields, "rejects_patient_scope": item.rejects_patient_scope})) for item in rows)
    body = {"registry_id": "evidence-lifecycle-adapters", "adapters": rows}
    return EvidenceLifecycleAdapterRegistry(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleAdapterReceipt", "EvidenceLifecycleAdapterRegistry", "EvidenceLifecycleInputAdapter", "default_evidence_lifecycle_adapters"]
