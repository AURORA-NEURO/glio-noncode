"""Operation contracts for the sequence grammar beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_public_data import SequenceGrammarOperation, SequenceGrammarState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarContract:
    operation: SequenceGrammarOperation
    title: str
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    allowed_states: tuple[SequenceGrammarState, ...]
    control_requirements: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.required_fields or not self.output_fields:
            raise ValidationError("sequence grammar contract is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "title": self.title,
                        "required_fields": self.required_fields,
                        "output_fields": self.output_fields,
                        "allowed_states": self.allowed_states,
                        "control_requirements": self.control_requirements,
                        "limitations": self.limitations,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarContractRegistry:
    contracts: tuple[SequenceGrammarContract, ...]
    registry_version: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.registry_version.strip() or not self.contracts:
            raise ValidationError("contract registry requires version and contracts")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "registry_version": self.registry_version,
                        "contracts": self.contracts,
                        "accepted": self.accepted,
                    }
                ),
            )

    def for_operation(self, operation: SequenceGrammarOperation) -> SequenceGrammarContract:
        for contract in self.contracts:
            if contract.operation is operation:
                return contract
        raise KeyError(operation)

    def manifest(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry_version,
            "accepted": self.accepted,
            "contract_count": len(self.contracts),
            "contracts": [contract.to_dict() for contract in self.contracts],
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.manifest()


def default_sequence_grammar_contracts() -> SequenceGrammarContractRegistry:
    states = tuple(SequenceGrammarState)
    common_outputs = (
        "state",
        "issue_codes",
        "measurements",
        "warnings",
        "content_address",
    )
    limitations = (
        "local sequence evidence is bounded by supplied windows and catalogs",
        "descriptive motif observations are not calibrated regulatory effects",
        "aggregate fixtures do not establish patient-level or clinical validity",
    )
    contracts = (
        SequenceGrammarContract(
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            "Motif disruption scanner",
            ("variant_id", "reference", "alternate", "motifs"),
            common_outputs,
            states,
            ("invalid alphabet", "empty window", "empty motif catalog", "loss retention"),
            limitations,
        ),
        SequenceGrammarContract(
            SequenceGrammarOperation.MOTIF_CREATION,
            "Motif creation scanner",
            ("variant_id", "reference", "alternate", "motifs"),
            common_outputs,
            states,
            ("invalid alphabet", "empty window", "empty motif catalog", "gain retention"),
            limitations,
        ),
        SequenceGrammarContract(
            SequenceGrammarOperation.SPACING_GRAMMAR,
            "Motif spacing and orientation grammar",
            ("hits", "rules"),
            common_outputs,
            states,
            ("empty hits", "unmatched rule", "invalid hit", "all compatible pairs"),
            limitations,
        ),
        SequenceGrammarContract(
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            "Cooperative transcription-factor grammar",
            ("sequence", "hits", "interactions", "model_id", "model_version"),
            common_outputs,
            states,
            (
                "invalid alphabet",
                "empty interactions",
                "required interaction missing",
                "contribution retention",
            ),
            limitations + ("weighted score is not a probability",),
        ),
    )
    return SequenceGrammarContractRegistry(
        contracts,
        registry_version="2026.08.d06-c05-c08.contracts.v1",
        accepted=len(contracts) == len(SequenceGrammarOperation),
    )


__all__ = [
    "SequenceGrammarContract",
    "SequenceGrammarContractRegistry",
    "default_sequence_grammar_contracts",
]
