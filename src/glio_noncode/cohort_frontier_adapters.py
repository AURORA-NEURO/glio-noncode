"""Strict row normalization adapters for cohort convergence operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .cohort_frontier_public_data import CohortFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierAdapterReceipt:
    operation: CohortFrontierOperation
    context_key: str
    source_ids: tuple[str, ...]
    row_count: int
    normalized_rows: tuple[dict[str, Any], ...]
    input_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierInputAdapter:
    adapter_id: str
    operation: CohortFrontierOperation
    accepted_fields: tuple[str, ...]
    boundary: str
    content_address: str

    def normalize(self, rows: list[Mapping[str, Any]], *, context_key: str, source_ids: tuple[str, ...] = ()) -> CohortFrontierAdapterReceipt:
        context_key = require_non_empty(context_key, "context_key")
        if not isinstance(rows, list):
            raise ValidationError("cohort adapter input must be a list")
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(rows, start=1):
            if not isinstance(raw, Mapping):
                raise ValidationError(f"cohort adapter row {index} must be an object")
            row = {field: raw[field] for field in self.accepted_fields if field in raw}
            row["context_key"] = str(raw.get("context_key", context_key)).strip()
            if row["context_key"] != context_key:
                raise ValidationError("cohort adapter context does not match")
            normalized.append(row)
        source_tuple = tuple(sorted({require_non_empty(str(item), "source_id") for item in source_ids}))
        body = {"operation": self.operation, "context_key": context_key, "source_ids": source_tuple, "row_count": len(normalized), "normalized_rows": tuple(normalized), "input_address": content_hash(tuple(normalized))}
        return CohortFrontierAdapterReceipt(**body, content_address=content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierAdapterRegistry:
    adapters: tuple[CohortFrontierInputAdapter, ...]
    content_address: str

    def __post_init__(self) -> None:
        if {item.operation for item in self.adapters} != set(CohortFrontierOperation):
            raise ValueError("cohort adapter registry must cover operations")

    def by_operation(self, operation: CohortFrontierOperation) -> CohortFrontierInputAdapter:
        return next(item for item in self.adapters if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_frontier_adapters() -> CohortFrontierAdapterRegistry:
    rows = (("cohort-fairness-adapter", CohortFrontierOperation.SUBGROUP_FAIRNESS, ("group", "positive", "context_key")), ("cohort-transport-adapter", CohortFrontierOperation.TRANSPORTABILITY, ("analysis_id", "source_features", "target_features", "shift_score", "context_key")), ("cohort-federated-adapter", CohortFrontierOperation.FEDERATED_SUMMARY, ("feature_id", "site_id", "count", "mean", "context_key")), ("cohort-discovery-adapter", CohortFrontierOperation.COHORT_DISCOVERY, ("feature_id", "weighted_mean", "context_key")))
    adapters = []
    for adapter_id, operation, fields in rows:
        body = {"adapter_id": adapter_id, "operation": operation, "accepted_fields": fields, "boundary": "public_aggregate_non_patient"}
        adapters.append(CohortFrontierInputAdapter(**body, content_address=content_hash(body)))
    return CohortFrontierAdapterRegistry(tuple(adapters), content_hash({"adapters": tuple(adapters)}))


__all__ = ["CohortFrontierAdapterReceipt", "CohortFrontierAdapterRegistry", "CohortFrontierInputAdapter", "default_cohort_frontier_adapters"]
