"""Contract-to-fixture validation matrix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_contracts import CohortBetaFrontierContractRegistry
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierValidationCell:
    operation: str
    contract_id: str
    positive_rows: int
    control_rows: int
    accepted_rows: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierValidationMatrix:
    cells: tuple[CohortBetaFrontierValidationCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_validation_matrix(contracts: CohortBetaFrontierContractRegistry, evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierValidationMatrix:
    cells = []
    for contract in contracts.contracts:
        rows = tuple(item for item in evaluation.rows if item.operation == contract.operation)
        positive = sum(item.expected_state.value == "supported" for item in rows)
        controls = len(rows) - positive
        accepted = sum(item.accepted for item in rows)
        body = {"operation": contract.operation, "contract_id": contract.capability_id, "positive": positive, "controls": controls, "accepted": accepted}
        cells.append(CohortBetaFrontierValidationCell(contract.operation, contract.capability_id, positive, controls, accepted, len(rows) == 4 and accepted == 4, content_hash(body, prefix="validation-cell")))
    values = tuple(cells)
    return CohortBetaFrontierValidationMatrix(values, all(item.accepted for item in values), content_hash(values, prefix="validation"))


__all__ = ["CohortBetaFrontierValidationCell", "CohortBetaFrontierValidationMatrix", "build_cohort_beta_frontier_validation_matrix"]
