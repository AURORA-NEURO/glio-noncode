"""Operation contracts for Domain 10 C09-C12 candidate link paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha import LinkGraphAlphaState
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierContract:
    contract_id: str
    capability_id: str
    operation: LinkGraphAlphaFrontierOperation
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    state_values: tuple[str, ...]
    issue_codes: tuple[str, ...]
    quality_floor: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierContractReport:
    contracts: tuple[LinkGraphAlphaFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_capability(self, capability_id: str) -> LinkGraphAlphaFrontierContract:
        for item in self.contracts:
            if item.capability_id == capability_id:
                return item
        raise KeyError(capability_id)

    def for_operation(self, operation: LinkGraphAlphaFrontierOperation | str) -> LinkGraphAlphaFrontierContract:
        value = LinkGraphAlphaFrontierOperation(str(operation))
        for item in self.contracts:
            if item.operation is value:
                return item
        raise KeyError(value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contracts": [item.to_dict() for item in self.contracts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_contracts() -> LinkGraphAlphaFrontierContractReport:
    states = tuple(item.value for item in LinkGraphAlphaState)
    contracts = (
        LinkGraphAlphaFrontierContract("GNC-D10-C09-contract", "GNC-D10-C09", LinkGraphAlphaFrontierOperation.CRISPR_PERTURBATION, ("observations", "variant_id", "element_id", "gene_id", "direction", "effect_size", "context_key", "public_aggregate"), ("link_count", "states", "supports", "evidence_ids"), states, ("context_mismatch", "direction_disagreement", "low_support", "single_method"), ("direction_retention", "context_gate", "weak_signal_visibility"), "Perturbation paths are candidate evidence and do not establish a regulatory mechanism."),
        LinkGraphAlphaFrontierContract("GNC-D10-C10-contract", "GNC-D10-C10", LinkGraphAlphaFrontierOperation.CONTACT_3D, ("observations", "variant_id", "element_id", "gene_id", "contact_signal", "resolution_bp", "assay_kind", "context_key", "public_aggregate"), ("link_count", "normalized_contacts", "resolution_bp", "assay_kinds", "alternative_genes"), states, ("context_mismatch", "weak_contact", "single_assay", "alternative_gene"), ("normalization", "resolution_retention", "alternative_visibility"), "Contact is an assay path and is not regulation proof."),
        LinkGraphAlphaFrontierContract("GNC-D10-C11-contract", "GNC-D10-C11", LinkGraphAlphaFrontierOperation.PROMOTER_TETHERING, ("observations", "distance_bp", "contact_support", "promoter_activity", "element_activity", "context_key", "public_aggregate"), ("scores", "tiers", "available_components", "alternative_genes"), states, ("context_mismatch", "missing_components", "tethering_ambiguity"), ("component_accounting", "distance_prior", "abstention"), "Tethering is a bounded baseline requiring external calibration."),
        LinkGraphAlphaFrontierContract("GNC-D10-C12-contract", "GNC-D10-C12", LinkGraphAlphaFrontierOperation.MULTI_GENE_GRAPH, ("evidence", "variant_id", "element_id", "gene_id", "link_type", "support", "context_key", "public_aggregate"), ("edge_count", "gene_count", "element_count", "component_count", "degree_by_node"), states, ("context_mismatch", "single_evidence", "contradictory_evidence"), ("edge_bookkeeping", "component_accounting", "alternative_visibility"), "Graph edges summarize declared evidence paths and do not select a preferred target."),
    )
    accepted = len(contracts) == 4 and all("public_aggregate" in item.required_fields for item in contracts)
    return LinkGraphAlphaFrontierContractReport(contracts, accepted)


__all__ = ["LinkGraphAlphaFrontierContract", "LinkGraphAlphaFrontierContractReport", "build_link_graph_alpha_frontier_contracts"]
