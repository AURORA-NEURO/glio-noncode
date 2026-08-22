"""Capability and output catalog for the D10 C09-C12 frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierCatalogEntry:
    capability_id: str
    operation: str
    title: str
    primitive: str
    input_boundary: str
    output_boundary: str
    state_values: tuple[str, ...]
    cli_command: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierCatalog:
    entries: tuple[LinkGraphAlphaFrontierCatalogEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_capability(self, capability_id: str) -> LinkGraphAlphaFrontierCatalogEntry:
        for item in self.entries:
            if item.capability_id == capability_id:
                return item
        raise KeyError(capability_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_catalog() -> LinkGraphAlphaFrontierCatalog:
    entries = (
        LinkGraphAlphaFrontierCatalogEntry("GNC-D10-C09", LinkGraphAlphaFrontierOperation.CRISPR_PERTURBATION.value, "CRISPR perturbation links", "CRISPRPerturbationLinker", "public aggregate perturbation observations", "candidate variant-element-gene links", ("partial", "contradictory", "out_of_domain"), "link-graph-alpha-frontier-evaluate"),
        LinkGraphAlphaFrontierCatalogEntry("GNC-D10-C10", LinkGraphAlphaFrontierOperation.CONTACT_3D.value, "3D contact links", "ThreeDContactLinker", "public aggregate contact observations", "candidate contact edges", ("partial", "out_of_domain"), "link-graph-alpha-frontier-evaluate"),
        LinkGraphAlphaFrontierCatalogEntry("GNC-D10-C11", LinkGraphAlphaFrontierOperation.PROMOTER_TETHERING.value, "promoter tethering baseline", "PromoterTetheringModel", "public aggregate tethering components", "scored tethering candidates", ("supported", "ambiguous", "abstained", "out_of_domain"), "link-graph-alpha-frontier-evaluate"),
        LinkGraphAlphaFrontierCatalogEntry("GNC-D10-C12", LinkGraphAlphaFrontierOperation.MULTI_GENE_GRAPH.value, "multi-gene element graph", "MultiGeneElementGraphBuilder", "public aggregate edge evidence", "context-qualified graph slice", ("supported", "partial", "contradictory", "out_of_domain"), "link-graph-alpha-frontier-evaluate"),
    )
    return LinkGraphAlphaFrontierCatalog(entries, len(entries) == 4 and len({item.capability_id for item in entries}) == 4)


__all__ = ["LinkGraphAlphaFrontierCatalog", "LinkGraphAlphaFrontierCatalogEntry", "build_link_graph_alpha_frontier_catalog"]
