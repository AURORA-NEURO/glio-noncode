"""Contract-to-fixture validation matrix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_contracts import CohortAlphaFrontierContractRegistry
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierValidationCell:
    operation: str
    contract_id: str
    rows: int
    supported_rows: int
    control_rows: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierValidationMatrix:
    cells: tuple[CohortAlphaFrontierValidationCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_validation_matrix(contracts: CohortAlphaFrontierContractRegistry, evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierValidationMatrix:
    cells = []
    for contract in contracts.contracts:
        rows = tuple(row for row in evaluation.rows if row.operation == contract.operation)
        supported = sum(row.expected_state.value == "supported" for row in rows)
        body = {"operation": contract.operation, "rows": len(rows), "supported": supported}
        cells.append(CohortAlphaFrontierValidationCell(contract.operation, contract.capability_id, len(rows), supported, len(rows) - supported, len(rows) == 4 and all(row.accepted for row in rows), content_hash(body, prefix="alpha-validation-cell")))
    values = tuple(cells)
    return CohortAlphaFrontierValidationMatrix(values, len(values) == 4 and all(item.accepted for item in values), content_hash(values, prefix="alpha-validation"))


__all__ = ["CohortAlphaFrontierValidationCell", "CohortAlphaFrontierValidationMatrix", "build_cohort_alpha_frontier_validation_matrix"]
