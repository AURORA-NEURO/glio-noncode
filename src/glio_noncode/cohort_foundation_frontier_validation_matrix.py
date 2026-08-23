"""Validation matrix connecting operation contracts to runtime evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_contracts import CohortFoundationContractRegistry
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_public_data import CohortFoundationOperation


@dataclass(frozen=True, slots=True)
class CohortFoundationValidationCell:
    cell_id: str
    operation: CohortFoundationOperation
    contract_fields_present: bool
    positive_present: bool
    control_present: bool
    review_boundary_present: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationValidationMatrix:
    matrix_id: str
    cells: tuple[CohortFoundationValidationCell, ...]
    accepted: bool
    content_address: str

    def by_operation(self, operation: CohortFoundationOperation) -> CohortFoundationValidationCell:
        return next(item for item in self.cells if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_validation_matrix(contracts: CohortFoundationContractRegistry, evaluation: CohortFoundationEvaluation) -> CohortFoundationValidationMatrix:
    cells = []
    for operation in CohortFoundationOperation:
        contract = contracts.by_operation(operation)
        values = tuple(item for item in evaluation.executions if item.operation is operation)
        positive = any(item.role.value == "positive" for item in values)
        control = any(item.role.value == "control" for item in values)
        review = any(item.actual_state != "supported" for item in values)
        body = {"operation": operation, "fields": contract.required_fields, "positive": positive, "control": control, "review": review}
        cells.append(CohortFoundationValidationCell(content_hash((operation.value, "validation"), prefix="cell"), operation, bool(contract.required_fields), positive, control, review, bool(contract.required_fields) and positive and control and review, content_hash(body)))
    body = {"matrix_id": "cohort-foundation-frontier-validation", "cells": cells}
    return CohortFoundationValidationMatrix(body["matrix_id"], tuple(cells), all(item.accepted for item in cells), content_hash(body))


__all__ = ["CohortFoundationValidationCell", "CohortFoundationValidationMatrix", "build_cohort_foundation_frontier_validation_matrix"]
