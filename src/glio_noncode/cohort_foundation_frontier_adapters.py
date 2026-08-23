"""Strict normalization adapters for the Domain 12 C01-C04 frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import ValidationError
from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_public_data import CohortFoundationOperation


@dataclass(frozen=True, slots=True)
class CohortFoundationAdapterReceipt:
    operation: CohortFoundationOperation
    adapter_id: str
    context_key: str
    input_count: int
    accepted_count: int
    rejected_count: int
    normalized_rows: tuple[Mapping[str, Any], ...]
    rejected_reasons: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationInputAdapter:
    adapter_id: str
    operation: CohortFoundationOperation
    required_fields: tuple[str, ...]
    row_field: str
    content_address: str

    def normalize(
        self,
        rows: list[Mapping[str, Any]],
        *,
        context_key: str,
    ) -> CohortFoundationAdapterReceipt:
        if not isinstance(rows, list):
            raise ValidationError("cohort foundation adapter input must be a list")
        normalized: list[Mapping[str, Any]] = []
        reasons: list[str] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                reasons.append(f"row_{index}:not_object")
                continue
            missing = tuple(field for field in self.required_fields if field not in row)
            if missing:
                reasons.append(f"row_{index}:missing:{','.join(missing)}")
                continue
            if row.get("context_key") not in (None, context_key):
                reasons.append(f"row_{index}:context_mismatch")
                continue
            normalized.append(dict(row))
        body = {
            "operation": self.operation,
            "adapter_id": self.adapter_id,
            "context_key": context_key,
            "input_count": len(rows),
            "accepted_count": len(normalized),
            "rejected_reasons": tuple(reasons),
        }
        return CohortFoundationAdapterReceipt(
            operation=self.operation,
            adapter_id=self.adapter_id,
            context_key=context_key,
            input_count=len(rows),
            accepted_count=len(normalized),
            rejected_count=len(reasons),
            normalized_rows=tuple(normalized),
            rejected_reasons=tuple(reasons),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class CohortFoundationAdapterRegistry:
    adapters: tuple[CohortFoundationInputAdapter, ...]
    content_address: str

    def __post_init__(self) -> None:
        operations = tuple(item.operation for item in self.adapters)
        if len(set(operations)) != len(operations) or set(operations) != set(CohortFoundationOperation):
            raise ValidationError("cohort foundation adapters must cover each operation once")

    def by_operation(self, operation: CohortFoundationOperation) -> CohortFoundationInputAdapter:
        for item in self.adapters:
            if item.operation is operation:
                return item
        raise ValidationError(f"no adapter for {operation.value}")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_foundation_frontier_adapters() -> CohortFoundationAdapterRegistry:
    definitions = (
        ("cohort-foundation-query-v1", CohortFoundationOperation.COHORT_QUERY, ("record_id", "variant_id", "context_key", "callable"), "rows"),
        ("cohort-foundation-background-v1", CohortFoundationOperation.BACKGROUND_RATE, ("record_id", "variant_id", "context_key"), "background_records"),
        ("cohort-foundation-sequence-v1", CohortFoundationOperation.SEQUENCE_CONTROL, ("record_id", "variant_id", "context_key", "sequence_context"), "candidates"),
        ("cohort-foundation-chromatin-v1", CohortFoundationOperation.CHROMATIN_CONTROL, ("record_id", "variant_id", "context_key", "chromatin_features"), "candidates"),
    )
    values = tuple(
        CohortFoundationInputAdapter(
            adapter_id=adapter_id,
            operation=operation,
            required_fields=required,
            row_field=row_field,
            content_address=content_hash((adapter_id, operation, required, row_field)),
        )
        for adapter_id, operation, required, row_field in definitions
    )
    return CohortFoundationAdapterRegistry(values, content_hash(values))


__all__ = [
    "CohortFoundationAdapterReceipt",
    "CohortFoundationAdapterRegistry",
    "CohortFoundationInputAdapter",
    "default_cohort_foundation_frontier_adapters",
]
