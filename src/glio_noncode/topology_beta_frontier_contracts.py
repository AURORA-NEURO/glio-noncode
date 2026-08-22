"""Operation contracts for the Domain 09 C05-C08 release boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_public_data import TopologyBetaFrontierOperation
from .topology_context import TopologyState


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierContract:
    contract_id: str
    capability_id: str
    operation: TopologyBetaFrontierOperation
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    state_values: tuple[str, ...]
    issue_codes: tuple[str, ...]
    quality_floor: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierContractReport:
    contracts: tuple[TopologyBetaFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_capability(self, capability_id: str) -> TopologyBetaFrontierContract:
        for item in self.contracts:
            if item.capability_id == capability_id:
                return item
        raise KeyError(capability_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contracts": [item.to_dict() for item in self.contracts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_contracts() -> TopologyBetaFrontierContractReport:
    states = tuple(item.value for item in TopologyState)
    contracts = (
        TopologyBetaFrontierContract("GNC-D09-C05-contract", "GNC-D09-C05", TopologyBetaFrontierOperation.LOOP_STRIPE, ("features", "feature_kind", "chromosome_a", "start_a", "end_a", "chromosome_b", "start_b", "end_b", "signal", "context_key", "source_version", "public_aggregate"), ("two_anchor_coordinates", "feature_kind", "signal", "resolution", "replicate_id", "caller", "raw_hash"), states, ("missing_loop_metadata", "replicate_disagreement", "context_mismatch"), ("coordinate_normalized", "source_receipt_present", "malformed_rows_quarantined"), "External caller calibration and complete schema conformance remain separate."),
        TopologyBetaFrontierContract("GNC-D09-C06-contract", "GNC-D09-C06", TopologyBetaFrontierOperation.PROMOTER_CAPTURE, ("contacts", "promoter_id", "target_element_id", "promoter_start", "target_start", "signal", "context_key", "source_version", "public_aggregate"), ("promoter_identity", "target_identity", "bait_id", "signal", "resolution", "raw_hash"), states, ("missing_bait_id", "replicate_disagreement", "context_mismatch"), ("coordinate_normalized", "source_receipt_present", "identity_preserved"), "Bait design, assay sensitivity, and cross-platform calibration remain separate."),
        TopologyBetaFrontierContract("GNC-D09-C07-contract", "GNC-D09-C07", TopologyBetaFrontierOperation.ENHANCER_PROMOTER_CONTACT, ("observations", "enhancer_id", "promoter_id", "signal", "context_key", "source_version", "public_aggregate"), ("median_signal", "signal_spread", "normalized_contact_score", "source_versions", "content_address"), states, ("no_contact_observations", "replicate_disagreement", "context_mismatch"), ("exact_context", "bounded_transform", "replicate_retention"), "The score is descriptive evidence and is not a probability or causal conclusion."),
        TopologyBetaFrontierContract("GNC-D09-C08-contract", "GNC-D09-C08", TopologyBetaFrontierOperation.ACTIVITY_BY_CONTACT, ("contacts", "activities", "model_id", "model_version", "context_key", "public_aggregate"), ("contact_component", "activity_component", "activity_by_contact_score", "missingness", "source_versions"), states, ("missing_activity", "component_disagreement", "context_mismatch"), ("component_retention", "model_receipt", "no_hidden_imputation"), "The product is a descriptive combination; calibration and transport evaluation remain open."),
    )
    accepted = len(contracts) == 4 and all("public_aggregate" in item.required_fields for item in contracts)
    return TopologyBetaFrontierContractReport(contracts, accepted)


__all__ = ["TopologyBetaFrontierContract", "TopologyBetaFrontierContractReport", "build_topology_beta_frontier_contracts"]
