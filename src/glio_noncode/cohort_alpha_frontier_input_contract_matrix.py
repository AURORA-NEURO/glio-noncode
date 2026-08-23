"""Input contract matrix separating identity, context, and measurement fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_contracts import CohortAlphaFrontierContractRegistry
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierInputContractCell:
    operation: str
    field: str
    field_class: str
    required: bool
    review_trigger: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierInputContractMatrix:
    cells: tuple[CohortAlphaFrontierInputContractCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_input_contract_matrix(contracts: CohortAlphaFrontierContractRegistry) -> CohortAlphaFrontierInputContractMatrix:
    cells = []
    for contract in contracts.contracts:
        for field in contract.required_fields:
            field_class = "context" if field == "context_key" else "identity" if field.endswith("_id") or field in {"variant_id", "sample_id"} else "measurement"
            cells.append(CohortAlphaFrontierInputContractCell(contract.operation, field, field_class, True, field in contract.review_triggers, content_hash({"operation": contract.operation, "field": field, "class": field_class, "required": True, "review": field in contract.review_triggers}, prefix="alpha-input-contract")))
    values = tuple(cells)
    return CohortAlphaFrontierInputContractMatrix(values, len(values) >= 20 and all(item.required for item in values), content_hash(values, prefix="alpha-input-contract-matrix"))


__all__ = ["CohortAlphaFrontierInputContractCell", "CohortAlphaFrontierInputContractMatrix", "build_cohort_alpha_frontier_input_contract_matrix"]
