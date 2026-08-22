"""Adapter registry for public aggregate Domain 13 inputs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_public_data import ValidationFrontierOperation


@dataclass(frozen=True, slots=True)
class ValidationFrontierAdapterReceipt:
    adapter_id: str
    operation: ValidationFrontierOperation
    accepted_fields: tuple[str, ...]
    boundary: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierInputAdapter:
    receipt: ValidationFrontierAdapterReceipt
    normalize: Callable[[dict[str, Any]], dict[str, Any]]

    def adapt(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.normalize(dict(payload))


@dataclass(frozen=True, slots=True)
class ValidationFrontierAdapterRegistry:
    adapters: tuple[ValidationFrontierInputAdapter, ...]
    content_address: str

    def by_operation(self, operation: ValidationFrontierOperation) -> ValidationFrontierInputAdapter:
        return next(item for item in self.adapters if item.receipt.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return {"adapters": [item.receipt.to_dict() for item in self.adapters], "content_address": self.content_address}


def _identity(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def default_validation_frontier_adapters() -> ValidationFrontierAdapterRegistry:
    adapters = []
    for operation in ValidationFrontierOperation:
        body = {"adapter_id": f"validation-{operation.value}-adapter", "operation": operation, "accepted_fields": ("context_key", "payload", "source_ids"), "boundary": "public_aggregate_non_patient"}
        receipt = ValidationFrontierAdapterReceipt(**body, content_address=content_hash(body))
        adapters.append(ValidationFrontierInputAdapter(receipt, _identity))
    body = {"adapters": tuple(adapters)}
    return ValidationFrontierAdapterRegistry(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierAdapterReceipt", "ValidationFrontierAdapterRegistry", "ValidationFrontierInputAdapter", "default_validation_frontier_adapters"]
