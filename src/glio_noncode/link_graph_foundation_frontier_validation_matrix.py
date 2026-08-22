"""Operation/role/state validation cells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierOperation
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierValidationCell:
    cell_id: str
    operation: str
    role: str
    state: str
    record_ids: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierValidationReport:
    cells: tuple[LinkGraphFoundationFrontierValidationCell, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cells": [item.to_dict() for item in self.cells], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_validation_matrix(evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierValidationReport:
    cells = tuple(LinkGraphFoundationFrontierValidationCell(f"{operation.value}:{role}:{state}", operation.value, role, state, tuple(row.record_id for row in evaluation.by_operation(operation.value) if row.role == role and row.observed_state == state), True) for operation in LinkGraphFoundationFrontierOperation for role in ("positive", "control") for state in sorted({row.observed_state for row in evaluation.by_operation(operation.value) if row.role == role}))
    checks = (check("cells", bool(cells), "validation cells exist"), check("operations", all(any(item.operation == operation.value for item in cells) for operation in LinkGraphFoundationFrontierOperation), "all operations are represented"), check("roles", all(any(item.role == role for item in cells) for role in ("positive", "control")), "positive and control roles are represented"))
    return LinkGraphFoundationFrontierValidationReport(cells, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierValidationCell", "LinkGraphFoundationFrontierValidationReport", "build_link_graph_foundation_frontier_validation_matrix"]
