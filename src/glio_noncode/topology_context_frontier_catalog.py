"""Capability catalog entries for Domain 09 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_public_data import TopologyContextFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierCatalogEntry:
    capability_id: str
    operation: TopologyContextFrontierOperation
    title: str
    module_count: int
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierCatalog:
    entries: tuple[TopologyContextFrontierCatalogEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> TopologyContextFrontierCatalogEntry:
        return next(item for item in self.entries if item.operation.value == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_catalog() -> TopologyContextFrontierCatalog:
    entries = tuple(
        TopologyContextFrontierCatalogEntry(
            f"GNC-D09-C0{index}", operation, title, 10, "public_aggregate_non_patient"
        )
        for index, (operation, title) in enumerate(
            (
                (
                    TopologyContextFrontierOperation.CONTACT_IMPORT,
                    "Contact import and context retrieval",
                ),
                (TopologyContextFrontierOperation.MATRIX_QC, "Contact matrix QC and normalization"),
                (TopologyContextFrontierOperation.BOUNDARY_ENSEMBLE, "TAD boundary ensemble"),
                (TopologyContextFrontierOperation.INSULATION_DELTA, "Insulation score delta"),
            ),
            start=1,
        )
    )
    return TopologyContextFrontierCatalog(entries, len(entries) == 4)


__all__ = [
    "TopologyContextFrontierCatalog",
    "TopologyContextFrontierCatalogEntry",
    "build_topology_context_frontier_catalog",
]
