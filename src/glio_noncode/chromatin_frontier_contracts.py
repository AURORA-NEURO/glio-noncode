"""Operation contracts for Domain 07 chromatin frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_frontier_public_data import (
    ChromatinFrontierOperation,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ChromatinFrontierContract:
    contract_id: str
    operation: ChromatinFrontierOperation
    adapter_name: str
    required_payload_fields: tuple[str, ...]
    positive_states: tuple[str, ...]
    control_states: tuple[str, ...]
    issue_vocabulary: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "contract_id",
            "adapter_name",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_payload_fields or not self.positive_states:
            raise ValueError("chromatin frontier contracts require fields and positive states")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierContractRegistry:
    contracts: tuple[ChromatinFrontierContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        operations = tuple(item.operation for item in self.contracts)
        if len(set(operations)) != len(operations):
            raise ValueError("chromatin frontier contract operations must be unique")
        if set(operations) != set(ChromatinFrontierOperation):
            raise ValueError("chromatin frontier contracts must cover all operations")

    def by_operation(self, operation: ChromatinFrontierOperation) -> ChromatinFrontierContract:
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
    operation: ChromatinFrontierOperation,
    adapter_name: str,
    required_payload_fields: tuple[str, ...],
    positive_states: tuple[str, ...],
    control_states: tuple[str, ...],
    issue_vocabulary: tuple[str, ...],
    prohibited_claims: tuple[str, ...],
) -> ChromatinFrontierContract:
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
    return ChromatinFrontierContract(**body, content_address=content_hash(body))


def default_chromatin_frontier_contracts() -> ChromatinFrontierContractRegistry:
    contracts = (
        _contract(
            "GNC-D07-C13-contract-v1",
            ChromatinFrontierOperation.CHROMATIN_SEGMENTATION,
            "ChromatinStateSegmentationAdapter",
            ("input_text", "low_signal", "high_signal"),
            ("supported",),
            ("ambiguous", "partial", "out_of_domain", "abstained"),
            ("context_mismatch", "invalid_segmentation_row", "invalid_segmentation_threshold"),
            ("clinical", "causal", "enhancer_truth"),
        ),
        _contract(
            "GNC-D07-C14-contract-v1",
            ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN,
            "AlleleSpecificChromatinAnalyzer",
            ("input_text", "ambiguity_tolerance", "delta_threshold"),
            ("supported",),
            ("ambiguous", "partial", "out_of_domain", "abstained"),
            ("context_mismatch", "invalid_allele_specific_row", "invalid_allele_threshold"),
            ("causal", "binding", "clinical"),
        ),
        _contract(
            "GNC-D07-C15-contract-v1",
            ChromatinFrontierOperation.EPIGENOMIC_PURITY,
            "EpigenomicPurityDeconvolver",
            ("input_text", "minimum_markers", "spread_tolerance"),
            ("supported",),
            ("ambiguous", "partial", "out_of_domain", "abstained"),
            ("context_mismatch", "invalid_purity_marker", "invalid_purity_parameter"),
            ("clinical", "purity_call", "tumor_fraction_truth"),
        ),
        _contract(
            "GNC-D07-C16-contract-v1",
            ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION,
            "BatchCellCompositionCorrector",
            ("input_text",),
            ("supported",),
            ("ambiguous", "partial", "out_of_domain", "abstained"),
            ("context_mismatch", "invalid_batch_composition_row", "invalid_batch_parameter"),
            ("causal", "corrected_truth", "clinical"),
        ),
    )
    return ChromatinFrontierContractRegistry(contracts, content_hash({"contracts": contracts}))


__all__ = [
    "ChromatinFrontierContract",
    "ChromatinFrontierContractRegistry",
    "default_chromatin_frontier_contracts",
]
