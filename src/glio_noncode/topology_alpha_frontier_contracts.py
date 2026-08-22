"""Operation contracts for the Domain 09 C09-C12 aggregate boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha import TopologyAlphaState
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierContract:
    contract_id: str
    capability_id: str
    operation: TopologyAlphaFrontierOperation
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    state_values: tuple[str, ...]
    issue_codes: tuple[str, ...]
    quality_floor: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierContractReport:
    contracts: tuple[TopologyAlphaFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_capability(self, capability_id: str) -> TopologyAlphaFrontierContract:
        for item in self.contracts:
            if item.capability_id == capability_id:
                return item
        raise KeyError(capability_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contracts": [item.to_dict() for item in self.contracts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_contracts() -> TopologyAlphaFrontierContractReport:
    states = tuple(item.value for item in TopologyAlphaState)
    contracts = (
        TopologyAlphaFrontierContract("GNC-D09-C09-contract", "GNC-D09-C09", TopologyAlphaFrontierOperation.BOUNDARY_MOTIF, ("records", "boundary_id", "side", "orientation", "score", "context_key", "public_aggregate"), ("relationship_labels", "left_orientations", "right_orientations", "median_score", "observation_ids"), states, ("context_mismatch", "orientation_ambiguity"), ("orientation_retention", "context_gate", "competing_labels_visible"), "Orientation is a boundary observation and is not insulation proof."),
        TopologyAlphaFrontierContract("GNC-D09-C10-contract", "GNC-D09-C10", TopologyAlphaFrontierOperation.CTCF_COHESIN, ("records", "variant_id", "reference_ctcf", "alternate_ctcf", "reference_cohesin", "alternate_cohesin", "context_key", "public_aggregate"), ("ctcf_delta", "cohesin_delta", "combined_delta", "disruption_label", "raw_hashes"), states, ("context_mismatch", "channel_disagreement"), ("channel_retention", "missingness", "delta_reproducibility"), "Channel deltas are descriptive comparisons without causal interpretation."),
        TopologyAlphaFrontierContract("GNC-D09-C11-contract", "GNC-D09-C11", TopologyAlphaFrontierOperation.IDH_INSULATOR, ("records", "region_id", "molecular_state", "insulator_score", "context_key", "public_aggregate"), ("insulator_delta", "dysfunction_index", "mutant_methylation", "wildtype_methylation", "label"), states, ("context_mismatch", "invalid_idh_insulator_row"), ("state_pair_gate", "methylation_separation", "missingness"), "Insulator and methylation channels remain separate descriptive evidence."),
        TopologyAlphaFrontierContract("GNC-D09-C12-contract", "GNC-D09-C12", TopologyAlphaFrontierOperation.SV_REWIRE, ("contacts", "events", "deleted_edge_ids", "gained_edge_ids", "rewired_edge_ids", "context_key", "public_aggregate"), ("preserved_edges", "lost_edges", "gained_edges", "rewired_edges", "affected_nodes"), states, ("context_mismatch",), ("edge_bookkeeping", "event_scope", "preserved_edges_visible"), "Edge simulation is deterministic bookkeeping and not a structure prediction."),
    )
    return TopologyAlphaFrontierContractReport(contracts, len(contracts) == 4 and all("public_aggregate" in item.required_fields for item in contracts))


__all__ = ["TopologyAlphaFrontierContract", "TopologyAlphaFrontierContractReport", "build_topology_alpha_frontier_contracts"]
