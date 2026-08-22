"""Operation adapter inventory for the sequence-effect frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_contracts import (
    SequenceEffectContractRegistry,
    default_sequence_effect_contracts,
)
from .sequence_effect_frontier_public_data import SequenceEffectOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectAdapterSpec:
    operation: SequenceEffectOperation
    adapter_name: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    contract_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "adapter_name": self.adapter_name,
                        "input_fields": self.input_fields,
                        "output_fields": self.output_fields,
                        "contract_address": self.contract_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectAdapterRegistry:
    adapters: tuple[SequenceEffectAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"adapters": self.adapters, "accepted": self.accepted}),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "adapters": [item.to_dict() for item in self.adapters],
            "content_address": self.content_address,
        }


def build_sequence_effect_adapters(
    contracts: SequenceEffectContractRegistry | None = None,
) -> SequenceEffectAdapterRegistry:
    contracts = contracts or default_sequence_effect_contracts()
    names = {
        SequenceEffectOperation.CONTEXT_ENCODING: "SequenceContextEncoder",
        SequenceEffectOperation.FOUNDATION_MODEL: "SequenceFoundationModelAdapter",
        SequenceEffectOperation.LONG_CONTEXT: "LongContextVariantEffectAdapter",
        SequenceEffectOperation.REGULATORY_ENSEMBLE: "RegulatoryTrackDeltaEnsemble",
    }
    adapters = tuple(
        SequenceEffectAdapterSpec(
            item.operation,
            names[item.operation],
            item.required_fields,
            item.output_fields,
            item.content_address,
        )
        for item in contracts.contracts
    )
    return SequenceEffectAdapterRegistry(
        adapters, len(adapters) == 4 and len({item.operation for item in adapters}) == 4
    )


__all__ = [
    "SequenceEffectAdapterRegistry",
    "SequenceEffectAdapterSpec",
    "build_sequence_effect_adapters",
]
