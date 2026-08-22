"""Closed operation contracts for the C05-C08 beta link plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph import LinkState
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierContract:
    contract_id: str
    capability_id: str
    operation: LinkGraphBetaFrontierOperation
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    issue_codes: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierContractReport:
    contracts: tuple[LinkGraphBetaFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_capability(self, capability_id: str) -> LinkGraphBetaFrontierContract:
        return next(item for item in self.contracts if item.capability_id == capability_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contracts": [item.to_dict() for item in self.contracts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_contracts() -> LinkGraphBetaFrontierContractReport:
    states = tuple(item.value for item in LinkState)
    contracts = (LinkGraphBetaFrontierContract("GNC-D10-C05-contract", "GNC-D10-C05", LinkGraphBetaFrontierOperation.ACTIVITY_CONTACT, ("observations", "activity_signal", "contact_signal", "context_key", "public_aggregate"), ("support", "link_count", "evidence_ids"), ("single_method", "replicate_pair", "missing_evidence", "context_mismatch"), "activity and contact are descriptive aggregate components"), LinkGraphBetaFrontierContract("GNC-D10-C06-contract", "GNC-D10-C06", LinkGraphBetaFrontierOperation.COACCESSIBILITY, ("observations", "score", "context_key", "public_aggregate"), ("gene_ids", "link_count", "evidence_ids"), ("single_method", "alternative_gene", "missing_evidence", "context_mismatch"), "coaccessibility is a candidate evidence path"), LinkGraphBetaFrontierContract("GNC-D10-C07-contract", "GNC-D10-C07", LinkGraphBetaFrontierOperation.MOLECULAR_QTL, ("observations", "effect_size", "p_value", "q_value", "public_aggregate"), ("bounded_support", "effect_size", "evidence_ids"), ("single_method", "weak_q_value", "missing_evidence", "context_mismatch"), "bounded p/q transforms are not causal inference"), LinkGraphBetaFrontierContract("GNC-D10-C08-contract", "GNC-D10-C08", LinkGraphBetaFrontierOperation.ALLELE_SPECIFIC, ("observations", "direction", "support", "context_key", "public_aggregate"), ("directions", "link_count", "evidence_ids"), ("single_direction", "direction_conflict", "missing_evidence", "context_mismatch"), "gain and loss retain visible direction conflict"))
    return LinkGraphBetaFrontierContractReport(contracts, len(contracts) == 4 and all(item.required_fields and item.output_fields and item.limitation and set(item.issue_codes) for item in contracts))


__all__ = ["LinkGraphBetaFrontierContract", "LinkGraphBetaFrontierContractReport", "build_link_graph_beta_frontier_contracts"]
