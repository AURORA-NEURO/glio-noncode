"""Input adapter declarations for mapping, JSON, and table callers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_public_data import GammaFrontierOperation


class GammaFrontierAdapterKind(StrEnum):
    """Supported input transport shapes."""

    MAPPING = "mapping"
    JSON = "json"
    TABLE = "table"


@dataclass(frozen=True, slots=True)
class GammaFrontierAdapterReceipt:
    """Receipt showing how a payload entered a surface."""

    operation: GammaFrontierOperation
    kind: GammaFrontierAdapterKind
    accepted: bool
    field_count: int
    normalized_keys: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierInputAdapter:
    """Declared adapter with required top-level fields."""

    operation: GammaFrontierOperation
    kind: GammaFrontierAdapterKind
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    content_address: str

    def adapt(self, payload: dict[str, Any]) -> GammaFrontierAdapterReceipt:
        keys = tuple(sorted(str(key) for key in payload))
        missing = tuple(field for field in self.required_fields if field not in payload)
        warnings = (f"missing required fields: {','.join(missing)}",) if missing else ()
        body = {
            "operation": self.operation,
            "kind": self.kind,
            "accepted": not missing,
            "field_count": len(keys),
            "normalized_keys": keys,
            "warnings": warnings,
        }
        return GammaFrontierAdapterReceipt(
            **body, content_address=content_hash(body, prefix="adapter")
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierAdapterRegistry:
    """Lookup registry for all operation and transport combinations."""

    adapters: tuple[GammaFrontierInputAdapter, ...]
    content_address: str

    def by_operation(
        self, operation: GammaFrontierOperation
    ) -> tuple[GammaFrontierInputAdapter, ...]:
        return tuple(item for item in self.adapters if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"adapter_count": len(self.adapters)}


def default_gamma_frontier_adapters() -> GammaFrontierAdapterRegistry:
    """Build adapters for each operation and each supported transport."""

    fields = {
        GammaFrontierOperation.EXPERIMENT_BOARD: ("cards",),
        GammaFrontierOperation.LAUNCH_PLAN: ("requests",),
        GammaFrontierOperation.SHAREABLE_SNAPSHOT: ("snapshot_payload", "context_key"),
        GammaFrontierOperation.COLLABORATION_ACCESS: ("members", "requests", "context_key"),
    }
    adapters = []
    for operation in GammaFrontierOperation:
        for kind in GammaFrontierAdapterKind:
            body = {
                "operation": operation,
                "kind": kind,
                "required_fields": fields[operation],
                "optional_fields": ("source_ids", "notes", "content_address"),
            }
            adapters.append(
                GammaFrontierInputAdapter(
                    **body, content_address=content_hash(body, prefix="adapter-definition")
                )
            )
    body = {"adapters": tuple(adapters)}
    return GammaFrontierAdapterRegistry(
        adapters=tuple(adapters), content_address=content_hash(body, prefix="adapter-registry")
    )


def adapt_gamma_frontier_input(
    operation: GammaFrontierOperation,
    payload: dict[str, Any],
    kind: GammaFrontierAdapterKind = GammaFrontierAdapterKind.MAPPING,
) -> GammaFrontierAdapterReceipt:
    """Adapt one mapping through its declared operation contract."""

    return next(
        item
        for item in default_gamma_frontier_adapters().adapters
        if item.operation is operation and item.kind is kind
    ).adapt(payload)


__all__ = [
    "GammaFrontierAdapterKind",
    "GammaFrontierAdapterReceipt",
    "GammaFrontierAdapterRegistry",
    "GammaFrontierInputAdapter",
    "adapt_gamma_frontier_input",
    "default_gamma_frontier_adapters",
]
