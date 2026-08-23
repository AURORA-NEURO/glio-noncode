"""Output contract matrix for state, disposition, and receipt fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOutputContractCell:
    operation: str
    output_field: str
    value_type: str
    populated_count: int
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOutputContractMatrix:
    cells: tuple[CohortAlphaFrontierOutputContractCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_output_contract_matrix(policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierOutputContractMatrix:
    cells = []
    for operation in ("C09", "C10", "C11", "C12"):
        rows = tuple(item for item in policy.decisions if item.operation == operation)
        for output_field, value_type in (("state", "CohortAlphaState"), ("disposition", "CohortAlphaFrontierDisposition"), ("rationale", "string"), ("content_address", "content address")):
            cells.append(CohortAlphaFrontierOutputContractCell(operation, output_field, value_type, len(rows), True, content_hash({"operation": operation, "field": output_field, "type": value_type, "count": len(rows)}, prefix="alpha-output-contract")))
    values = tuple(cells)
    return CohortAlphaFrontierOutputContractMatrix(values, len(values) == 16 and all(item.populated_count == 4 and item.required for item in values), content_hash(values, prefix="alpha-output-contract-matrix"))


__all__ = ["CohortAlphaFrontierOutputContractCell", "CohortAlphaFrontierOutputContractMatrix", "build_cohort_alpha_frontier_output_contract_matrix"]
