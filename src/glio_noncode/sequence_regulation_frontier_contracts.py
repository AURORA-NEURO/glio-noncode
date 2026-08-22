"""Executable contracts for the C09-C12 aggregate evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationOperation,
    SequenceRegulationState,
)
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class SequenceRegulationContract:
    operation: SequenceRegulationOperation
    required_fields: tuple[str, ...]
    prohibited_fields: tuple[str, ...]
    allowed_states: tuple[SequenceRegulationState, ...]
    boundary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.required_fields or not self.boundary:
            raise ValidationError("contract fields and boundary are required")
        if not self.allowed_states:
            raise ValidationError("contract needs allowed states")
        if not self.content_address:
            object.__setattr__(
                self, "content_address", content_hash(self.to_dict(include_address=False))
            )

    def to_dict(self, *, include_address: bool = True) -> dict[str, Any]:
        result = {
            "operation": self.operation.value,
            "required_fields": list(self.required_fields),
            "prohibited_fields": list(self.prohibited_fields),
            "allowed_states": [state.value for state in self.allowed_states],
            "boundary": self.boundary,
        }
        if include_address:
            result["content_address"] = self.content_address
        return result


@dataclass(frozen=True, slots=True)
class SequenceRegulationContractReport:
    contracts: tuple[SequenceRegulationContract, ...]
    accepted: bool
    unique_operations: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.contracts:
            raise ValidationError("contract report cannot be empty")
        if not self.content_address:
            object.__setattr__(
                self, "content_address", content_hash(self.to_dict(include_address=False))
            )

    def to_dict(self, *, include_address: bool = True) -> dict[str, Any]:
        result = {
            "accepted": self.accepted,
            "unique_operations": self.unique_operations,
            "contracts": [contract.to_dict() for contract in self.contracts],
        }
        if include_address:
            result["content_address"] = self.content_address
        return result


def build_sequence_regulation_contracts(
    boundary: str = "public_aggregate_non_patient",
) -> SequenceRegulationContractReport:
    states = tuple(SequenceRegulationState)
    contracts = (
        SequenceRegulationContract(
            SequenceRegulationOperation.NUCLEOSOME_PROPENSITY,
            ("sequence", "context_key"),
            ("patient", "subject"),
            states,
            boundary,
        ),
        SequenceRegulationContract(
            SequenceRegulationOperation.SPLICE_REGULATION,
            ("reference_sequence", "alternate_sequence", "motifs"),
            ("patient", "subject"),
            states,
            boundary,
        ),
        SequenceRegulationContract(
            SequenceRegulationOperation.UTR_REGULATION,
            ("region", "sequence", "motifs"),
            ("patient", "subject"),
            states,
            boundary,
        ),
        SequenceRegulationContract(
            SequenceRegulationOperation.PROMOTER_GRAMMAR,
            ("sequence", "motifs", "rules"),
            ("patient", "subject"),
            states,
            boundary,
        ),
    )
    return SequenceRegulationContractReport(
        contracts=contracts,
        accepted=len({contract.operation for contract in contracts})
        == len(SequenceRegulationOperation),
        unique_operations=len({contract.operation for contract in contracts}),
    )


__all__ = [
    "SequenceRegulationContract",
    "SequenceRegulationContractReport",
    "build_sequence_regulation_contracts",
]
