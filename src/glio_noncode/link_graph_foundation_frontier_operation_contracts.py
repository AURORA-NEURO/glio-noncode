"""Per-operation contracts and explicit limitations for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierOperationContract:
    operation: str
    purpose: str
    required_inputs: tuple[str, ...]
    output_fields: tuple[str, ...]
    supported_states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierOperationContractCatalog:
    contracts: tuple[LinkGraphFoundationFrontierOperationContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> LinkGraphFoundationFrontierOperationContract:
        return next(item for item in self.contracts if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contracts": [item.to_dict() for item in self.contracts], "operation_count": len(self.contracts), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_operation_contracts() -> LinkGraphFoundationFrontierOperationContractCatalog:
    states = ("supported", "absent", "ambiguous", "abstained", "partial", "contradictory", "out_of_domain")
    contracts = (LinkGraphFoundationFrontierOperationContract(LinkGraphFoundationFrontierOperation.COORDINATE_OVERLAP.value, "assign a variant to overlapping regulatory elements", ("variant", "elements", "context_key"), ("link_count", "element_id", "state"), states, ("multiple_overlaps", "no_overlap", "context_mismatch"), ("coordinate proximity alone does not establish function", "aggregate elements are not patient records")), LinkGraphFoundationFrontierOperationContract(LinkGraphFoundationFrontierOperation.NEAREST_GENE.value, "select the nearest gene inside a bounded interval", ("variant", "genes", "max_distance_bp", "context_key"), ("gene_id", "distance_bp", "state"), states, ("distance_tie", "distance_window", "context_mismatch"), ("nearest is a baseline, not causal proof", "ties require abstention")), LinkGraphFoundationFrontierOperationContract(LinkGraphFoundationFrontierOperation.CCRE_ASSIGNMENT.value, "assign an overlapping candidate regulatory element", ("variant", "elements", "context_key"), ("element_id", "element_count", "state"), states, ("multiple_ccres", "no_ccre", "context_mismatch"), ("element labels are source-defined", "absence is not evidence of biological absence")), LinkGraphFoundationFrontierOperationContract(LinkGraphFoundationFrontierOperation.CONSENSUS.value, "combine independent aggregate evidence methods", ("variant_id", "evidence", "context_key"), ("link_count", "methods", "state"), states, ("single_method", "contradictory_evidence", "context_mismatch"), ("consensus is limited to declared methods", "contradiction remains visible")))
    return LinkGraphFoundationFrontierOperationContractCatalog(contracts, len(contracts) == len(tuple(LinkGraphFoundationFrontierOperation)) and all(item.required_inputs and item.output_fields and item.limitations for item in contracts))


def operation_contract_summary(catalog: LinkGraphFoundationFrontierOperationContractCatalog) -> dict[str, Any]:
    return {"operation_count": len(catalog.contracts), "required_input_count": sum(len(item.required_inputs) for item in catalog.contracts), "output_field_count": sum(len(item.output_fields) for item in catalog.contracts), "limitation_count": sum(len(item.limitations) for item in catalog.contracts), "accepted": catalog.accepted}


__all__ = ["LinkGraphFoundationFrontierOperationContract", "LinkGraphFoundationFrontierOperationContractCatalog", "build_link_graph_foundation_frontier_operation_contracts", "operation_contract_summary"]
