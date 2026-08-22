"""Typed input adapters and operation registry for the causal frontier."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .causal_frontier_public_data import CausalFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierAdapterReceipt:
    operation: CausalFrontierOperation
    context_key: str
    source_ids: tuple[str, ...]
    row_count: int
    normalized_rows: tuple[dict[str, Any], ...]
    input_address: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.context_key, "context_key")
        if self.row_count != len(self.normalized_rows):
            raise ValueError("adapter row count must match normalized rows")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierInputAdapter:
    adapter_id: str
    operation: CausalFrontierOperation
    accepted_fields: tuple[str, ...]
    required_fields: tuple[str, ...]
    boundary: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.adapter_id, "adapter_id")
        require_non_empty(self.boundary, "boundary")
        if not self.accepted_fields:
            raise ValueError("adapter needs accepted fields")

    def normalize(
        self,
        rows: list[Mapping[str, Any]],
        *,
        context_key: str,
        source_ids: tuple[str, ...] = (),
    ) -> CausalFrontierAdapterReceipt:
        context_key = require_non_empty(context_key, "context_key")
        if not isinstance(rows, list):
            raise ValidationError("adapter input must be a list")
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(rows, start=1):
            if not isinstance(raw, Mapping):
                raise ValidationError(f"adapter row {index} must be an object")
            missing = tuple(field for field in self.required_fields if field not in raw)
            if missing:
                raise ValidationError(f"adapter row {index} is missing fields: {', '.join(missing)}")
            row = {field: raw[field] for field in self.accepted_fields if field in raw}
            row["context_key"] = str(raw.get("context_key", context_key)).strip()
            if row["context_key"] != context_key:
                raise ValidationError("adapter context does not match request")
            normalized.append(row)
        source_tuple = tuple(sorted({require_non_empty(str(item), "source_id") for item in source_ids}))
        body = {
            "operation": self.operation,
            "context_key": context_key,
            "source_ids": source_tuple,
            "row_count": len(normalized),
            "normalized_rows": tuple(normalized),
            "input_address": content_hash(tuple(normalized)),
        }
        return CausalFrontierAdapterReceipt(**body, content_address=content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierAdapterRegistry:
    adapters: tuple[CausalFrontierInputAdapter, ...]
    content_address: str

    def __post_init__(self) -> None:
        operations = tuple(item.operation for item in self.adapters)
        if len(set(operations)) != len(operations):
            raise ValueError("adapter operations must be unique")
        if set(operations) != set(CausalFrontierOperation):
            raise ValueError("adapter registry must cover every operation")

    def by_operation(self, operation: CausalFrontierOperation) -> CausalFrontierInputAdapter:
        return next(item for item in self.adapters if item.operation is operation)

    def by_id(self, adapter_id: str) -> CausalFrontierInputAdapter:
        return next(item for item in self.adapters if item.adapter_id == adapter_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _adapter(
    adapter_id: str,
    operation: CausalFrontierOperation,
    accepted_fields: tuple[str, ...],
    required_fields: tuple[str, ...],
) -> CausalFrontierInputAdapter:
    body = {
        "adapter_id": adapter_id,
        "operation": operation,
        "accepted_fields": accepted_fields,
        "required_fields": required_fields,
        "boundary": "public_aggregate_non_patient",
    }
    return CausalFrontierInputAdapter(**body, content_address=content_hash(body))


def default_causal_frontier_adapters() -> CausalFrontierAdapterRegistry:
    adapters = (
        _adapter("causal-posterior-adapter", CausalFrontierOperation.POSTERIOR_DECOMPOSITION, ("hypothesis_id", "prior", "likelihood", "measurement", "dependency_penalty", "context_key"), ()),
        _adapter("causal-driver-adapter", CausalFrontierOperation.DRIVER_POSTERIOR, ("driver_id", "evidence_ids", "evidence_support", "prior", "context_key"), ()),
        _adapter("causal-prediction-adapter", CausalFrontierOperation.SELECTIVE_PREDICTION, ("prediction_id", "score", "uncertainty", "context_key"), ()),
        _adapter("causal-dossier-adapter", CausalFrontierOperation.DOSSIER_PUBLICATION, ("hypothesis_id", "evidence_address", "context_key"), ()),
    )
    return CausalFrontierAdapterRegistry(adapters, content_hash({"adapters": adapters}))


__all__ = [
    "CausalFrontierAdapterReceipt",
    "CausalFrontierAdapterRegistry",
    "CausalFrontierInputAdapter",
    "default_causal_frontier_adapters",
]
