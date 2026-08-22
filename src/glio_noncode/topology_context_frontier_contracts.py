"""Operation contracts for Domain 09 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_public_data import TopologyContextFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierContract:
    contract_id: str
    operation: TopologyContextFrontierOperation
    required_fields: tuple[str, ...]
    state_values: tuple[str, ...]
    issue_values: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierContractReport:
    contracts: tuple[TopologyContextFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> TopologyContextFrontierContract:
        return next(item for item in self.contracts if item.operation.value == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "contracts": [item.to_dict() for item in self.contracts],
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_contracts() -> TopologyContextFrontierContractReport:
    states = ("supported", "partial", "ambiguous", "out_of_domain", "abstained", "invalid")
    contracts = (
        TopologyContextFrontierContract(
            "GNC-D09-C01-contract",
            TopologyContextFrontierOperation.CONTACT_IMPORT,
            ("contacts", "target_context_key", "public_aggregate"),
            states,
            ("invalid_contact_row", "context_mismatch", "no_contact_rows"),
            "Contacts are measured topology observations and retain assay/context gates.",
        ),
        TopologyContextFrontierContract(
            "GNC-D09-C02-contract",
            TopologyContextFrontierOperation.MATRIX_QC,
            ("contacts", "target_context_key", "normalization_method", "public_aggregate"),
            states,
            ("invalid_contact_row", "context_mismatch", "no_contact_rows"),
            "QC exposes duplicates and zeroes without hidden matrix correction.",
        ),
        TopologyContextFrontierContract(
            "GNC-D09-C03-contract",
            TopologyContextFrontierOperation.BOUNDARY_ENSEMBLE,
            ("boundaries", "target_context_key", "public_aggregate"),
            states,
            ("invalid_boundary_row", "context_mismatch"),
            "Boundary clusters preserve competing calls and assay identity.",
        ),
        TopologyContextFrontierContract(
            "GNC-D09-C04-contract",
            TopologyContextFrontierOperation.INSULATION_DELTA,
            ("measurement", "target_context_key", "public_aggregate"),
            states,
            ("missing_insulation_score", "invalid_insulation_score", "context_mismatch"),
            "Insulation deltas are descriptive comparisons with missingness guards.",
        ),
    )
    return TopologyContextFrontierContractReport(contracts=contracts, accepted=True)


__all__ = [
    "TopologyContextFrontierContract",
    "TopologyContextFrontierContractReport",
    "build_topology_context_frontier_contracts",
]
