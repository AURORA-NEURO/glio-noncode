"""Input adapter registry for serialized C05-C08 payloads."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_public_data import BetaFrontierOperation


class BetaFrontierAdapterKind(StrEnum):
    JSON = "json"
    MAPPING = "mapping"
    NOTEBOOK = "notebook"
    CSV = "csv"


@dataclass(frozen=True, slots=True)
class BetaFrontierAdapterReceipt:
    adapter_id: str
    operation: BetaFrontierOperation
    kind: BetaFrontierAdapterKind
    accepted_fields: tuple[str, ...]
    rejected_fields: tuple[str, ...]
    normalization_steps: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.adapter_id, "adapter_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierInputAdapter:
    adapter_id: str
    operation: BetaFrontierOperation
    kind: BetaFrontierAdapterKind
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    forbidden_fields: tuple[str, ...]
    content_address: str

    def adapt(self, payload: dict[str, Any]) -> BetaFrontierAdapterReceipt:
        keys = set(payload)
        accepted = tuple(sorted(keys.intersection(self.required_fields + self.optional_fields)))
        rejected = tuple(sorted(keys.intersection(self.forbidden_fields)))
        steps = ("preserve exact context", "retain unknown fields for review", "address normalized receipt")
        body = {"adapter_id": self.adapter_id, "operation": self.operation, "kind": self.kind, "accepted_fields": accepted, "rejected_fields": rejected, "normalization_steps": steps}
        return BetaFrontierAdapterReceipt(**body, content_address=content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierAdapterRegistry:
    adapters: tuple[BetaFrontierInputAdapter, ...]
    content_address: str

    def by_operation(self, operation: BetaFrontierOperation) -> tuple[BetaFrontierInputAdapter, ...]:
        return tuple(item for item in self.adapters if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_beta_frontier_adapters() -> BetaFrontierAdapterRegistry:
    adapters = (
        BetaFrontierInputAdapter("topology-json", BetaFrontierOperation.TOPOLOGY_VIEWPORT, BetaFrontierAdapterKind.JSON, ("context_key", "loops", "contacts"), ("contact_scores", "activity_results", "focus_start", "focus_end"), ("clinical_label",), content_hash("topology-json")),
        BetaFrontierInputAdapter("causal-mapping", BetaFrontierOperation.CAUSAL_CHAIN, BetaFrontierAdapterKind.MAPPING, ("context_key", "results"), ("chain_id",), ("clinical_probability",), content_hash("causal-mapping")),
        BetaFrontierInputAdapter("posterior-notebook", BetaFrontierOperation.POSTERIOR_DECOMPOSITION, BetaFrontierAdapterKind.NOTEBOOK, ("context_key", "posterior", "components"), ("residual_tolerance",), ("treatment_decision",), content_hash("posterior-notebook")),
        BetaFrontierInputAdapter("table-csv", BetaFrontierOperation.EVIDENCE_TABLE, BetaFrontierAdapterKind.CSV, ("context_key", "workspace", "filter"), ("export_columns",), ("patient_identifier",), content_hash("table-csv")),
    )
    body = {"adapters": adapters}
    return BetaFrontierAdapterRegistry(adapters=adapters, content_address=content_hash(body))


def adapt_beta_frontier_input(operation: BetaFrontierOperation, payload: dict[str, Any], kind: BetaFrontierAdapterKind = BetaFrontierAdapterKind.MAPPING) -> BetaFrontierAdapterReceipt:
    registry = default_beta_frontier_adapters()
    adapter = next(item for item in registry.adapters if item.operation is operation and item.kind is kind)
    return adapter.adapt(payload)


__all__ = ["BetaFrontierAdapterKind", "BetaFrontierAdapterReceipt", "BetaFrontierAdapterRegistry", "BetaFrontierInputAdapter", "adapt_beta_frontier_input", "default_beta_frontier_adapters"]
