"""Capability catalog for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierCatalogEntry:
    capability_id: str
    operation: TopologyAlphaFrontierOperation
    title: str
    public_scope: str
    adapter_id: str
    state_values: tuple[str, ...]
    release_status: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierCatalog:
    entries: tuple[TopologyAlphaFrontierCatalogEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> TopologyAlphaFrontierCatalogEntry:
        for item in self.entries:
            if item.operation.value == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_catalog() -> TopologyAlphaFrontierCatalog:
    states = ("supported", "partial", "ambiguous", "abstained", "invalid", "out_of_domain", "contradictory")
    entries = (TopologyAlphaFrontierCatalogEntry("GNC-D09-C09", TopologyAlphaFrontierOperation.BOUNDARY_MOTIF, "Boundary motif orientation", "public aggregate motif records", "d09-c09-boundary-motif", states, "verified"), TopologyAlphaFrontierCatalogEntry("GNC-D09-C10", TopologyAlphaFrontierOperation.CTCF_COHESIN, "CTCF cohesin disruption comparison", "public aggregate channel records", "d09-c10-ctcf-cohesin", states, "verified"), TopologyAlphaFrontierCatalogEntry("GNC-D09-C11", TopologyAlphaFrontierOperation.IDH_INSULATOR, "IDH insulator comparison", "public aggregate state records", "d09-c11-idh-insulator", states, "verified"), TopologyAlphaFrontierCatalogEntry("GNC-D09-C12", TopologyAlphaFrontierOperation.SV_REWIRE, "SV contact edge simulation", "public aggregate edge and event records", "d09-c12-sv-rewire", states, "verified"))
    return TopologyAlphaFrontierCatalog(entries, len(entries) == 4 and len({item.capability_id for item in entries}) == 4)


__all__ = ["TopologyAlphaFrontierCatalog", "TopologyAlphaFrontierCatalogEntry", "build_topology_alpha_frontier_catalog"]
