"""Cross-product validation matrix for operation, role, state, and boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierOperation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierValidationCell:
    cell_id: str
    operation: str
    role: str
    state: str
    record_ids: tuple[str, ...]
    passed: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierValidationReport:
    cells: tuple[LinkGraphAlphaFrontierValidationCell, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def cells_for(self, operation: str) -> tuple[LinkGraphAlphaFrontierValidationCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cells": [item.to_dict() for item in self.cells], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_validation_matrix(evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierValidationReport:
    cells = []
    for operation in LinkGraphAlphaFrontierOperation:
        rows = evaluation.by_operation(operation.value)
        for role in ("positive", "control"):
            selected = tuple(item for item in rows if item.role == role)
            for state in sorted({item.observed_state for item in selected}):
                records = tuple(item.record_id for item in selected if item.observed_state == state)
                cells.append(LinkGraphAlphaFrontierValidationCell(f"{operation.value}:{role}:{state}", operation.value, role, state, records, bool(records), "observed replay state has at least one row"))
    values = tuple(cells)
    checks = (check("matrix_nonempty", bool(values), "validation matrix has cells"), check("operations_covered", all(any(item.operation == operation.value for item in values) for operation in LinkGraphAlphaFrontierOperation), "all operations are represented"), check("positive_covered", all(any(item.operation == operation.value and item.role == "positive" for item in values) for operation in LinkGraphAlphaFrontierOperation), "all positive paths are represented"), check("control_covered", all(any(item.operation == operation.value and item.role == "control" for item in values) for operation in LinkGraphAlphaFrontierOperation), "all control paths are represented"))
    return LinkGraphAlphaFrontierValidationReport(values, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierValidationCell", "LinkGraphAlphaFrontierValidationReport", "build_link_graph_alpha_frontier_validation_matrix"]
