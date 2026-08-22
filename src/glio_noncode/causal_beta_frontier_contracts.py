"""Closed operation contracts for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_public_data import CausalBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierContract:
    contract_id: str
    capability_id: str
    operation: CausalBetaFrontierOperation
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    issue_codes: tuple[str, ...]
    limitation: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contract_id": self.contract_id, "capability_id": self.capability_id, "operation": self.operation, "required_fields": self.required_fields, "output_fields": self.output_fields, "issue_codes": self.issue_codes, "limitation": self.limitation}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierContractReport:
    contracts: tuple[CausalBetaFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_capability(self, capability_id: str) -> CausalBetaFrontierContract:
        return next(item for item in self.contracts if item.capability_id == capability_id)

    def for_operation(self, operation: CausalBetaFrontierOperation | str) -> CausalBetaFrontierContract:
        value = CausalBetaFrontierOperation(str(operation))
        return next(item for item in self.contracts if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contracts": [item.to_dict() for item in self.contracts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_contracts() -> CausalBetaFrontierContractReport:
    contracts = (
        CausalBetaFrontierContract("causal-beta-c05-contract", "GNC-D11-C05", CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, ("source_node", "target_node", "context_key", "evidence"), ("state", "support", "uncertainty", "sensitivity", "evidence_ids"), ("minimum_independent_sources", "contradictory_direction", "context_mismatch"), "independent mediator paths are a bounded evidence summary"),
        CausalBetaFrontierContract("causal-beta-c06-contract", "GNC-D11-C06", CausalBetaFrontierOperation.ELEMENT_TO_GENE, ("source_node", "target_node", "context_key", "evidence"), ("state", "support", "uncertainty", "evidence_ids"), ("minimum_independent_sources", "contradictory_direction", "context_mismatch"), "element-to-gene support is not a calibrated gene effect"),
        CausalBetaFrontierContract("causal-beta-c07-contract", "GNC-D11-C07", CausalBetaFrontierOperation.GENE_TO_STATE, ("source_node", "target_node", "context_key", "evidence"), ("state", "support", "uncertainty", "negative_evidence_ids"), ("minimum_independent_sources", "negative_control_conflict", "context_mismatch"), "gene-to-state association is not a perturbation result"),
        CausalBetaFrontierContract("causal-beta-c08-contract", "GNC-D11-C08", CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, ("state_id", "context_key", "observations"), ("state", "reference_value", "alternate_value", "delta_alternate_minus_reference", "sensitivity"), ("missing_alternate_allele", "replicate_ambiguity", "context_mismatch"), "alternate-minus-reference delta is descriptive"),
    )
    return CausalBetaFrontierContractReport(contracts, len(contracts) == 4 and {item.operation for item in contracts} == set(CausalBetaFrontierOperation))


__all__ = ["CausalBetaFrontierContract", "CausalBetaFrontierContractReport", "build_causal_beta_frontier_contracts"]
