"""Closed operation contracts for Domain 11 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_public_data import CausalFoundationFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierContract:
    contract_id: str
    capability_id: str
    operation: CausalFoundationFrontierOperation
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    issue_codes: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierContractReport:
    contracts: tuple[CausalFoundationFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_capability(self, capability_id: str) -> CausalFoundationFrontierContract:
        return next(item for item in self.contracts if item.capability_id == capability_id)

    def for_operation(self, operation: CausalFoundationFrontierOperation | str) -> CausalFoundationFrontierContract:
        value = CausalFoundationFrontierOperation(str(operation))
        return next(item for item in self.contracts if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contracts": [item.to_dict() for item in self.contracts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_foundation_frontier_contracts() -> CausalFoundationFrontierContractReport:
    contracts = (
        CausalFoundationFrontierContract("GNC-D11-C01-contract", "GNC-D11-C01", CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, ("hypothesis_id", "variant_id", "element_id", "gene_id", "state_id", "mechanism", "factors", "profile", "features", "measurements"), ("state", "support_proxy", "uncertainty", "factor_ids", "missing_evidence"), ("missing_prior_feature", "contradictory_factor_edge", "context_mismatch"), "support_proxy is a research-only product of declared proxies"),
        CausalFoundationFrontierContract("GNC-D11-C02-contract", "GNC-D11-C02", CausalFoundationFrontierOperation.FACTOR_GRAPH, ("factors", "context_key", "graph_id"), ("active_factor_ids", "superseded_factor_ids", "orphan_factor_ids", "contradictory_edge_ids", "state"), ("orphan_factor_lineage", "contradictory_factor_edge", "context_mismatch"), "history is append-only and superseded factors remain visible"),
        CausalFoundationFrontierContract("GNC-D11-C03-contract", "GNC-D11-C03", CausalFoundationFrontierOperation.CONTEXT_PRIOR, ("profile", "features", "context_key"), ("prior_score", "feature_contributions", "missing_features", "out_of_range_features", "uncertainty"), ("missing_prior_feature", "prior_feature_out_of_range", "context_mismatch"), "prior_score is bounded but not calibrated probability"),
        CausalFoundationFrontierContract("GNC-D11-C04-contract", "GNC-D11-C04", CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, ("edge_id", "measurements", "context_key"), ("likelihood_proxy", "channel_groups", "measurement_ids", "missing_measurement_ids", "uncertainty"), ("single_measurement_group", "contradictory_measurement", "context_mismatch"), "likelihood_proxy is dependence-adjusted descriptive evidence"),
    )
    return CausalFoundationFrontierContractReport(contracts, len(contracts) == 4 and {item.operation for item in contracts} == set(CausalFoundationFrontierOperation))


__all__ = ["CausalFoundationFrontierContract", "CausalFoundationFrontierContractReport", "build_causal_foundation_frontier_contracts"]
