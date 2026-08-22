"""Input/output contracts for Domain 06 C01–C04."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_effect_frontier_public_data import SequenceEffectOperation, SequenceEffectState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectContract:
    operation: SequenceEffectOperation
    capability_ids: tuple[str, ...]
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    states: tuple[SequenceEffectState, ...]
    issue_codes: tuple[str, ...]
    boundary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.capability_ids or not self.required_fields or not self.output_fields:
            raise ValidationError("contracts require capability, input, and output fields")
        if not self.boundary.strip():
            raise ValidationError("contract boundary is required")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "capability_ids": self.capability_ids,
                        "required_fields": self.required_fields,
                        "output_fields": self.output_fields,
                        "states": self.states,
                        "issue_codes": self.issue_codes,
                        "boundary": self.boundary,
                    }
                ),
            )

    def validate(self, payload: Mapping[str, Any]) -> tuple[str, ...]:
        if not isinstance(payload, Mapping):
            return ("payload-not-object",)
        return tuple(f"missing:{field}" for field in self.required_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return {**jsonable(self), "states": [state.value for state in self.states]}


@dataclass(frozen=True, slots=True)
class SequenceEffectContractRegistry:
    contracts: tuple[SequenceEffectContract, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        operations = tuple(item.operation for item in self.contracts)
        if len(set(operations)) != len(operations):
            raise ValidationError("contract operations must be unique")
        if set(operations) != set(SequenceEffectOperation):
            raise ValidationError("contracts must cover all four sequence-effect operations")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(tuple(item.to_dict() for item in self.contracts)),
            )

    def get(self, operation: SequenceEffectOperation) -> SequenceEffectContract:
        for contract in self.contracts:
            if contract.operation is operation:
                return contract
        raise ValidationError(f"unknown sequence-effect operation: {operation}")

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for contract in self.contracts for code in contract.issue_codes}))

    def manifest(self) -> dict[str, Any]:
        return {
            "contracts": [item.to_dict() for item in self.contracts],
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.manifest()


def default_sequence_effect_contracts() -> SequenceEffectContractRegistry:
    common_states = tuple(SequenceEffectState)
    return SequenceEffectContractRegistry(
        contracts=(
            SequenceEffectContract(
                SequenceEffectOperation.CONTEXT_ENCODING,
                ("GNC-D06-C01",),
                ("sequence_id", "source_id", "sequence"),
                ("sequence_hash", "gc_fraction", "kmer_frequencies"),
                common_states,
                ("invalid_alphabet", "empty_sequence", "ambiguous_bases"),
                "bounded-sequence-context",
            ),
            SequenceEffectContract(
                SequenceEffectOperation.FOUNDATION_MODEL,
                ("GNC-D06-C02",),
                ("source_id", "text"),
                ("observations", "issues", "input_hash"),
                common_states,
                ("invalid_effect_row", "missing_model_id", "delta_mismatch"),
                "declared-model-output",
            ),
            SequenceEffectContract(
                SequenceEffectOperation.LONG_CONTEXT,
                ("GNC-D06-C03",),
                ("source_id", "text"),
                ("observations", "issues", "input_hash"),
                common_states,
                ("context_too_short", "invalid_effect_row", "empty_effect_input"),
                "minimum-1024-context",
            ),
            SequenceEffectContract(
                SequenceEffectOperation.REGULATORY_ENSEMBLE,
                ("GNC-D06-C04",),
                ("observations",),
                ("rows", "mean_delta", "disagreement"),
                common_states,
                ("single_model", "model_disagreement", "no_observations"),
                "delta-is-not-probability",
            ),
        )
    )


__all__ = [
    "SequenceEffectContract",
    "SequenceEffectContractRegistry",
    "default_sequence_effect_contracts",
]
