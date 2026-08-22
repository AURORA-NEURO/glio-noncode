"""Operation contracts for the D07 C05-C08 evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_public_data import MethylationFrontierOperation, MethylationFrontierState
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class MethylationFrontierContract:
    operation: MethylationFrontierOperation
    required_fields: tuple[str, ...]
    prohibited_fields: tuple[str, ...]
    allowed_states: tuple[MethylationFrontierState, ...]
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
class MethylationFrontierContractReport:
    contracts: tuple[MethylationFrontierContract, ...]
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


def build_methylation_frontier_contracts(
    boundary: str = "public_aggregate_non_patient",
) -> MethylationFrontierContractReport:
    states = tuple(MethylationFrontierState)
    contracts = (
        MethylationFrontierContract(
            MethylationFrontierOperation.CONTEXT_RETRIEVAL,
            ("text", "source_id", "query", "context_key"),
            ("patient", "subject"),
            states,
            boundary,
        ),
        MethylationFrontierContract(
            MethylationFrontierOperation.CPG_CHANGE,
            ("reference_sequence", "alternate_sequence", "variant_id"),
            ("patient", "subject"),
            states,
            boundary,
        ),
        MethylationFrontierContract(
            MethylationFrontierOperation.SENSITIVE_MOTIF,
            ("sequence", "motifs", "methylation_records"),
            ("patient", "subject"),
            states,
            boundary,
        ),
        MethylationFrontierContract(
            MethylationFrontierOperation.IDH_CONTEXT,
            ("target_records", "comparator_records", "model_id", "model_version"),
            ("patient", "subject"),
            states,
            boundary,
        ),
    )
    return MethylationFrontierContractReport(
        contracts=contracts,
        accepted=len({contract.operation for contract in contracts})
        == len(MethylationFrontierOperation),
        unique_operations=len({contract.operation for contract in contracts}),
    )


__all__ = [
    "MethylationFrontierContract",
    "MethylationFrontierContractReport",
    "build_methylation_frontier_contracts",
]
