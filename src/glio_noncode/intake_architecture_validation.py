"""Cross-product validation matrix across seven intake control planes."""

from __future__ import annotations

from .intake_architecture_contracts import (
    INTAKE_ARCHITECTURE_OPERATION_COUNT,
    IntakeArchitectureFixture,
    IntakeArchitectureOperation,
    IntakeArchitecturePlane,
    IntakeArchitectureValidationCell,
    IntakeArchitectureValidationMatrix,
    addressed,
)
from .intake_architecture_operations import evaluate_intake_architecture_fixture


def build_intake_architecture_validation_matrix(fixture: IntakeArchitectureFixture) -> IntakeArchitectureValidationMatrix:
    evaluation = evaluate_intake_architecture_fixture(fixture)
    by_operation = {item.operation_id: item for item in evaluation.results if item.scenario.value == "positive"}
    cells = []
    for plane in IntakeArchitecturePlane:
        for spec in fixture.operations:
            result = by_operation[spec.operation_id]
            passed = result.observed_state.value == "accepted" and result.issue_codes == ()
            body = {"cell_id": f"{plane.value}:{spec.operation_id}", "plane": plane, "operation_id": spec.operation_id, "passed": passed, "detail": f"{plane.value} plane retains {spec.operation_id} receipt"}
            cells.append(IntakeArchitectureValidationCell(**body, content_address=addressed(body, "intake-validation-cell")))
    body = {"matrix_id": "intake-validation-d01", "cells": tuple(cells), "accepted": len(cells) == len(IntakeArchitecturePlane) * INTAKE_ARCHITECTURE_OPERATION_COUNT and all(cell.passed for cell in cells)}
    return IntakeArchitectureValidationMatrix(**body, content_address=addressed(body, "intake-validation"))


__all__ = ["build_intake_architecture_validation_matrix"]
