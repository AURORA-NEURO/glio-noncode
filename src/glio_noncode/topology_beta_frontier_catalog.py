"""Capability catalog for the four Domain 09 beta operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_public_data import TopologyBetaFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierCatalogEntry:
    capability_id: str
    operation: TopologyBetaFrontierOperation
    title: str
    public_scope: str
    adapter_id: str
    state_values: tuple[str, ...]
    release_status: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierCatalog:
    entries: tuple[TopologyBetaFrontierCatalogEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> TopologyBetaFrontierCatalogEntry:
        for item in self.entries:
            if item.operation.value == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_catalog() -> TopologyBetaFrontierCatalog:
    states = ("supported", "partial", "ambiguous", "absent", "abstained", "out_of_domain")
    entries = (
        TopologyBetaFrontierCatalogEntry("GNC-D09-C05", TopologyBetaFrontierOperation.LOOP_STRIPE, "Loop and stripe feature normalization", "public aggregate feature records", "d09-c05-loop-stripe", states, "verified"),
        TopologyBetaFrontierCatalogEntry("GNC-D09-C06", TopologyBetaFrontierOperation.PROMOTER_CAPTURE, "Promoter capture contact normalization", "public aggregate bait-to-element records", "d09-c06-promoter-capture", states, "verified"),
        TopologyBetaFrontierCatalogEntry("GNC-D09-C07", TopologyBetaFrontierOperation.ENHANCER_PROMOTER_CONTACT, "Enhancer promoter contact scoring", "public aggregate contact evidence", "d09-c07-enhancer-promoter", states, "verified"),
        TopologyBetaFrontierCatalogEntry("GNC-D09-C08", TopologyBetaFrontierOperation.ACTIVITY_BY_CONTACT, "Activity by contact component scoring", "public aggregate activity and contact evidence", "d09-c08-activity-by-contact", states, "verified"),
    )
    return TopologyBetaFrontierCatalog(entries, len(entries) == 4 and len({item.capability_id for item in entries}) == 4)


__all__ = ["TopologyBetaFrontierCatalog", "TopologyBetaFrontierCatalogEntry", "build_topology_beta_frontier_catalog"]
