"""Closed operation contracts for coordinate, proximity, cCRE, and consensus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph import LinkState
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierContract:
    contract_id: str
    capability_id: str
    operation: LinkGraphFoundationFrontierOperation
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    issue_codes: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierContractReport:
    contracts: tuple[LinkGraphFoundationFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_capability(self, capability_id: str) -> LinkGraphFoundationFrontierContract:
        for item in self.contracts:
            if item.capability_id == capability_id:
                return item
        raise KeyError(capability_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contracts": [item.to_dict() for item in self.contracts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_contracts() -> LinkGraphFoundationFrontierContractReport:
    states = tuple(item.value for item in LinkState)
    contracts = (LinkGraphFoundationFrontierContract("GNC-D10-C01-contract", "GNC-D10-C01", LinkGraphFoundationFrontierOperation.COORDINATE_OVERLAP, ("variant", "elements", "context_key", "public_aggregate"), ("link_count", "element_ids", "alternative_genes"), ("context_mismatch", "multiple_overlaps", "no_overlap"), "Overlap creates candidate relationships only."), LinkGraphFoundationFrontierContract("GNC-D10-C02-contract", "GNC-D10-C02", LinkGraphFoundationFrontierOperation.NEAREST_GENE, ("variant", "genes", "max_distance_bp", "context_key", "public_aggregate"), ("link_count", "distances_bp", "gene_ids"), ("context_mismatch", "distance_tie", "distance_window"), "Distance is a transparent baseline and not a target claim."), LinkGraphFoundationFrontierContract("GNC-D10-C03-contract", "GNC-D10-C03", LinkGraphFoundationFrontierOperation.CCRE_ASSIGNMENT, ("variant", "elements", "context_key", "public_aggregate"), ("element_count", "element_ids", "reason"), ("context_mismatch", "multiple_ccres", "no_ccre"), "cCRE assignment keeps every overlapping candidate."), LinkGraphFoundationFrontierContract("GNC-D10-C04-contract", "GNC-D10-C04", LinkGraphFoundationFrontierOperation.CONSENSUS, ("evidence", "variant_id", "context_key", "public_aggregate"), ("link_count", "methods", "gene_ids", "alternative_genes"), ("context_mismatch", "single_method", "contradictory_evidence"), "Consensus groups declared paths and is not mechanism proof."))
    return LinkGraphFoundationFrontierContractReport(contracts, len(contracts) == 4 and all("public_aggregate" in item.required_fields for item in contracts))


__all__ = ["LinkGraphFoundationFrontierContract", "LinkGraphFoundationFrontierContractReport", "build_link_graph_foundation_frontier_contracts"]
