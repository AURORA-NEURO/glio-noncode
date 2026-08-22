"""Operation contracts for the Domain 08 beta prior tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_public_data import CellContextBetaFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierContract:
    contract_id: str
    operation: CellContextBetaFrontierOperation
    required_fields: tuple[str, ...]
    accepted_states: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    refusal_conditions: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.contract_id or not self.required_fields or not self.accepted_states:
            raise ValidationError("beta contract is incomplete")
        if not self.evidence_requirements or not self.refusal_conditions:
            raise ValidationError("beta contract needs evidence and refusal conditions")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierContractReport:
    contracts: tuple[CellContextBetaFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.contracts) != 4:
            raise ValidationError("beta contract report must contain four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def unique_operations(self) -> int:
        return len({item.operation for item in self.contracts})

    def for_operation(
        self, operation: CellContextBetaFrontierOperation
    ) -> CellContextBetaFrontierContract:
        return next(item for item in self.contracts if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_beta_frontier_contracts(
    boundary: str = "public_aggregate_non_patient",
) -> CellContextBetaFrontierContractReport:
    states = ("supported", "partial", "ambiguous", "contradictory", "out_of_domain", "abstained")
    common = ("observation_text", "target_context_key", "model_version", "ambiguity_margin")
    contracts = (
        CellContextBetaFrontierContract(
            "GNC-D08-C05-contract",
            CellContextBetaFrontierOperation.DEVELOPMENTAL_LINEAGE,
            common,
            states,
            ("exact context", "versioned rows", "candidate alternatives"),
            ("context drift", "empty evidence", "uncalibrated score"),
        ),
        CellContextBetaFrontierContract(
            "GNC-D08-C06-contract",
            CellContextBetaFrontierOperation.GBM_MALIGNANT_STATE,
            common,
            states,
            ("explicit GBM context", "malignant state candidates", "contradiction retention"),
            ("generic glioma context", "disease gate failure", "diagnostic interpretation"),
        ),
        CellContextBetaFrontierContract(
            "GNC-D08-C07-contract",
            CellContextBetaFrontierOperation.IDH_MUTANT_LINEAGE,
            common + ("declared_molecular_state",),
            states,
            ("IDH-mutant gate", "exact context", "source versions"),
            ("IDH-wildtype gate", "missing declaration", "calibration claim"),
        ),
        CellContextBetaFrontierContract(
            "GNC-D08-C08-contract",
            CellContextBetaFrontierOperation.H3K27_DEVELOPMENTAL_STATE,
            common + ("declared_molecular_state",),
            states,
            ("H3K27-altered gate", "developmental alternatives", "ambiguity margin"),
            ("wrong molecular gate", "missing declaration", "clinical developmental claim"),
        ),
    )
    accepted = (
        boundary == "public_aggregate_non_patient"
        and len({item.operation for item in contracts}) == 4
    )
    return CellContextBetaFrontierContractReport(contracts, accepted)


__all__ = [
    "CellContextBetaFrontierContract",
    "CellContextBetaFrontierContractReport",
    "build_cell_context_beta_frontier_contracts",
]
