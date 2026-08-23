"""Machine-readable schema manifest for lifecycle beta records and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierFieldSpec:
    name: str
    value_type: str
    required: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierSchema:
    schema_id: str
    version: str
    fields: tuple[LifecycleBetaFrontierFieldSpec, ...]
    operations: tuple[LifecycleBetaFrontierOperation, ...]
    state_values: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_lifecycle_beta_frontier_schema() -> LifecycleBetaFrontierSchema:
    fields = (
        LifecycleBetaFrontierFieldSpec("record_id", "string", True, "stable fixture record identifier"),
        LifecycleBetaFrontierFieldSpec("operation", "enum", True, "one of eight lifecycle operations"),
        LifecycleBetaFrontierFieldSpec("role", "enum", True, "positive or control"),
        LifecycleBetaFrontierFieldSpec("context_key", "string", True, "exact graph context"),
        LifecycleBetaFrontierFieldSpec("payload", "object", True, "operation-specific aggregate input"),
        LifecycleBetaFrontierFieldSpec("expected_state", "enum", True, "declared boundary state"),
        LifecycleBetaFrontierFieldSpec("expected_issue_codes", "array", True, "declared issue vocabulary"),
        LifecycleBetaFrontierFieldSpec("content_address", "sha256", True, "immutable receipt"),
    )
    body = {"schema_id": "lifecycle-beta-frontier-schema", "version": "2026.08.v1", "fields": fields, "operations": tuple(LifecycleBetaFrontierOperation), "state_values": tuple(item.value for item in __import__("glio_noncode.lifecycle_beta_frontier_contracts", fromlist=["LifecycleBetaFrontierState"]).LifecycleBetaFrontierState)}
    return LifecycleBetaFrontierSchema(**body, content_address=content_hash(body))


def validate_lifecycle_beta_frontier_schema(schema: LifecycleBetaFrontierSchema | None = None) -> bool:
    schema = schema or default_lifecycle_beta_frontier_schema()
    return len(schema.fields) == 8 and len(schema.operations) == 8 and len(schema.state_values) >= 12 and len({item.name for item in schema.fields}) == len(schema.fields) and schema.content_address.startswith("sha256:")


__all__ = ["LifecycleBetaFrontierFieldSpec", "LifecycleBetaFrontierSchema", "default_lifecycle_beta_frontier_schema", "validate_lifecycle_beta_frontier_schema"]
