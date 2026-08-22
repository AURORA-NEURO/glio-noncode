"""Operation contracts for Domain 08 cell-state frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_state_frontier_public_data import CellStateFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CellStateFrontierContract:
    contract_id: str
    operation: CellStateFrontierOperation
    adapter_name: str
    required_payload_fields: tuple[str, ...]
    positive_states: tuple[str, ...]
    control_states: tuple[str, ...]
    issue_vocabulary: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("contract_id", "adapter_name", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_payload_fields or not self.positive_states:
            raise ValueError("cell state contracts require fields and positive states")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierContractRegistry:
    contracts: tuple[CellStateFrontierContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        operations = tuple(item.operation for item in self.contracts)
        if len(set(operations)) != len(operations):
            raise ValueError("cell state contract operations must be unique")
        if set(operations) != set(CellStateFrontierOperation):
            raise ValueError("cell state contracts must cover all operations")

    def by_operation(self, operation: CellStateFrontierOperation) -> CellStateFrontierContract:
        for contract in self.contracts:
            if contract.operation is operation:
                return contract
        raise KeyError(operation)

    def manifest(self) -> dict[str, Any]:
        return {
            "contracts": [item.to_dict() for item in self.contracts],
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _contract(
    contract_id: str,
    operation: CellStateFrontierOperation,
    adapter_name: str,
    required_payload_fields: tuple[str, ...],
    positive_states: tuple[str, ...],
    control_states: tuple[str, ...],
    issue_vocabulary: tuple[str, ...],
    prohibited_claims: tuple[str, ...],
) -> CellStateFrontierContract:
    body = {
        "contract_id": contract_id,
        "operation": operation,
        "adapter_name": adapter_name,
        "required_payload_fields": required_payload_fields,
        "positive_states": positive_states,
        "control_states": control_states,
        "issue_vocabulary": issue_vocabulary,
        "prohibited_claims": prohibited_claims,
    }
    return CellStateFrontierContract(**body, content_address=content_hash(body))


def default_cell_state_frontier_contracts() -> CellStateFrontierContractRegistry:
    contracts = (
        _contract(
            "GNC-D08-C13-contract-v1",
            CellStateFrontierOperation.ABUNDANCE_INTERVAL,
            "CellStateAbundanceUncertaintyModel",
            ("input_text", "interval_multiplier"),
            ("supported",),
            ("partial", "out_of_domain", "abstained", "invalid"),
            ("context_mismatch", "invalid_cell_count", "invalid_interval_multiplier"),
            ("clinical", "diagnostic", "tumor_fraction_truth"),
        ),
        _contract(
            "GNC-D08-C14-contract-v1",
            CellStateFrontierOperation.REFERENCE_MAPPING,
            "SingleCellReferenceMapper",
            ("input_text", "minimum_score", "minimum_margin"),
            ("supported",),
            ("partial", "out_of_domain", "abstained", "invalid"),
            ("context_mismatch", "ambiguous_reference_mapping", "no_reference_scores"),
            ("clinical", "diagnostic", "cell_identity_truth"),
        ),
        _contract(
            "GNC-D08-C15-contract-v1",
            CellStateFrontierOperation.OOD_DETECTION,
            "CellStateOODDetector",
            ("input_text", "maximum_distance", "minimum_support"),
            ("supported",),
            ("partial", "out_of_domain", "abstained", "invalid"),
            ("context_mismatch", "cell_state_out_of_domain", "invalid_cell_state_row"),
            ("clinical", "diagnostic", "territory_truth"),
        ),
        _contract(
            "GNC-D08-C16-contract-v1",
            CellStateFrontierOperation.CONTEXT_PUBLICATION,
            "CellStateContextPublisher",
            ("input_text", "cell_ids", "mapping_address", "abundance_address", "ood_address"),
            ("supported",),
            ("partial", "out_of_domain", "abstained", "invalid"),
            ("context_mismatch", "empty_cell_ids", "missing_receipt_address"),
            ("clinical", "diagnostic", "treatment", "actionability"),
        ),
    )
    return CellStateFrontierContractRegistry(contracts, content_hash({"contracts": contracts}))


__all__ = [
    "CellStateFrontierContract",
    "CellStateFrontierContractRegistry",
    "default_cell_state_frontier_contracts",
]
