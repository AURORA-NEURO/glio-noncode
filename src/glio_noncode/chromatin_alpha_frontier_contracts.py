"""Operation contracts for the Domain 07 C09-C12 chromatin tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierContract:
    operation: ChromatinAlphaFrontierOperation
    required_fields: tuple[str, ...]
    prohibited_fields: tuple[str, ...]
    allowed_states: tuple[str, ...]
    boundary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.required_fields or not self.allowed_states or not self.boundary:
            raise ValidationError("contract fields, states, and boundary are required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierContractReport:
    contracts: tuple[ChromatinAlphaFrontierContract, ...]
    accepted: bool
    unique_operations: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.contracts) != len(ChromatinAlphaFrontierOperation):
            raise ValidationError("contract report must contain four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation: ChromatinAlphaFrontierOperation
    ) -> ChromatinAlphaFrontierContract:
        for contract in self.contracts:
            if contract.operation is operation:
                return contract
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_alpha_frontier_contracts(
    boundary: str = "public_aggregate_non_patient",
) -> ChromatinAlphaFrontierContractReport:
    states = ("supported", "partial", "ambiguous", "out_of_domain", "invalid", "abstained")
    contracts = (
        ChromatinAlphaFrontierContract(
            ChromatinAlphaFrontierOperation.SEGMENTATION,
            ("input_text", "low_signal", "high_signal", "context_key"),
            ("patient", "subject", "sample_id"),
            states,
            boundary,
        ),
        ChromatinAlphaFrontierContract(
            ChromatinAlphaFrontierOperation.ALLELE_SPECIFIC,
            ("input_text", "ambiguity_tolerance", "delta_threshold", "context_key"),
            ("patient", "subject", "sample_id"),
            states,
            boundary,
        ),
        ChromatinAlphaFrontierContract(
            ChromatinAlphaFrontierOperation.PURITY,
            ("input_text", "minimum_markers", "spread_tolerance", "context_key"),
            ("patient", "subject", "sample_id"),
            states,
            boundary,
        ),
        ChromatinAlphaFrontierContract(
            ChromatinAlphaFrontierOperation.COMPOSITION_CORRECTION,
            ("input_text", "batch_offsets", "target_composition", "context_key"),
            ("patient", "subject", "sample_id"),
            states,
            boundary,
        ),
    )
    unique = len({contract.operation for contract in contracts})
    return ChromatinAlphaFrontierContractReport(contracts, unique == 4, unique)


__all__ = [
    "ChromatinAlphaFrontierContract",
    "ChromatinAlphaFrontierContractReport",
    "build_chromatin_alpha_frontier_contracts",
]
