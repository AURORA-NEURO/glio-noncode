"""Operation contracts for Domain 08 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierContract:
    contract_id: str
    operation: CellContextAlphaFrontierOperation
    required_fields: tuple[str, ...]
    accepted_states: tuple[str, ...]
    retained_dimensions: tuple[str, ...]
    refusal_conditions: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.contract_id
            or not self.required_fields
            or not self.accepted_states
            or not self.retained_dimensions
            or not self.refusal_conditions
        ):
            raise ValidationError("alpha contract is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierContractReport:
    contracts: tuple[CellContextAlphaFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.contracts) != 4:
            raise ValidationError("alpha contract report requires four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def unique_operations(self) -> int:
        return len({item.operation for item in self.contracts})

    def for_operation(
        self, operation: CellContextAlphaFrontierOperation
    ) -> CellContextAlphaFrontierContract:
        return next(item for item in self.contracts if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_alpha_frontier_contracts(
    boundary: str = "public_aggregate_non_patient",
) -> CellContextAlphaFrontierContractReport:
    states = (
        "supported",
        "partial",
        "ambiguous",
        "out_of_domain",
        "abstained",
        "contradictory",
        "invalid",
    )
    common = ("observation_text", "target_context_key")
    contracts = (
        CellContextAlphaFrontierContract(
            "GNC-D08-C09-contract",
            CellContextAlphaFrontierOperation.SPATIAL_NICHE,
            common + ("ambiguity_margin",),
            states,
            ("niche", "support", "samples", "margin"),
            ("context mismatch", "close candidate", "invalid support"),
        ),
        CellContextAlphaFrontierContract(
            "GNC-D08-C10-contract",
            CellContextAlphaFrontierOperation.CORE_MARGIN,
            common + ("ambiguity_tolerance",),
            states,
            ("core", "margin", "delta", "territory label"),
            ("context mismatch", "one-sided score", "near tie"),
        ),
        CellContextAlphaFrontierContract(
            "GNC-D08-C11-contract",
            CellContextAlphaFrontierOperation.RECURRENCE_STATE,
            common + ("ambiguity_margin",),
            states,
            ("phase", "rank", "phase margin", "support"),
            ("context mismatch", "phase disagreement", "invalid support"),
        ),
        CellContextAlphaFrontierContract(
            "GNC-D08-C12-contract",
            CellContextAlphaFrontierOperation.TREATMENT_INDUCED,
            common + ("induction_threshold",),
            states,
            ("baseline", "post support", "delta", "induction label"),
            ("context mismatch", "missing baseline", "clinical response interpretation"),
        ),
    )
    return CellContextAlphaFrontierContractReport(
        contracts, boundary == "public_aggregate_non_patient"
    )


__all__ = [
    "CellContextAlphaFrontierContract",
    "CellContextAlphaFrontierContractReport",
    "build_cell_context_alpha_frontier_contracts",
]
