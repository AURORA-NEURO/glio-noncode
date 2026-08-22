"""Typed contracts for the Domain 08 context release boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_public_data import CellContextFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierContract:
    contract_id: str
    operation: CellContextFrontierOperation
    input_shape: tuple[str, ...]
    output_shape: tuple[str, ...]
    refusal_paths: tuple[str, ...]
    evidence_boundary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.contract_id
            or not self.input_shape
            or not self.output_shape
            or not self.refusal_paths
        ):
            raise ValidationError("cell context contract is incomplete")
        if not self.evidence_boundary:
            raise ValidationError("cell context contract needs an evidence boundary")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierContractReport:
    contracts: tuple[CellContextFrontierContract, ...]
    accepted: bool
    unique_operations: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.contracts) != 4:
            raise ValidationError("four cell context contracts are required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(self, operation: CellContextFrontierOperation) -> CellContextFrontierContract:
        for item in self.contracts:
            if item.operation is operation:
                return item
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_contracts(
    evidence_boundary: str = "public_aggregate_non_patient",
) -> CellContextFrontierContractReport:
    common = ("context_mismatch", "malformed_row", "missing_dimension", "unsupported_transport")
    contracts = (
        CellContextFrontierContract(
            "d08-c01-disease",
            CellContextFrontierOperation.DISEASE_ONTOLOGY,
            ("observation_text", "context_key", "source_receipt"),
            ("state", "candidates", "evidence_ids", "uncertainty"),
            common,
            evidence_boundary,
        ),
        CellContextFrontierContract(
            "d08-c02-age",
            CellContextFrontierOperation.AGE_ROUTE,
            ("observation_text", "context_key", "source_receipt"),
            ("state", "route", "conflict", "uncertainty"),
            common + ("unknown_age",),
            evidence_boundary,
        ),
        CellContextFrontierContract(
            "d08-c03-molecular",
            CellContextFrontierOperation.MOLECULAR_STATE,
            ("observation_text", "context_key", "source_receipt"),
            ("state", "class_state", "molecular_state", "uncertainty"),
            common,
            evidence_boundary,
        ),
        CellContextFrontierContract(
            "d08-c04-assembly",
            CellContextFrontierOperation.TERRITORY_ASSEMBLY,
            ("observation_text", "context_key", "source_receipt"),
            ("state", "territory", "assembled_context", "uncertainty"),
            common + ("ambiguous_territory",),
            evidence_boundary,
        ),
    )
    accepted = (
        evidence_boundary == "public_aggregate_non_patient"
        and len({item.operation for item in contracts}) == 4
    )
    return CellContextFrontierContractReport(
        contracts, accepted, len({item.operation for item in contracts})
    )


__all__ = [
    "CellContextFrontierContract",
    "CellContextFrontierContractReport",
    "build_cell_context_frontier_contracts",
]
