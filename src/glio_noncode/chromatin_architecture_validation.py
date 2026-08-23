"""Plane-by-operation validation matrix for D07."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import (
    ChromatinArchitectureCheck,
    ChromatinArchitectureCheckKind,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    ChromatinArchitecturePlane,
    addressed,
)
from .serialization import jsonable

CHROMATIN_ARCHITECTURE_PLANES = tuple(ChromatinArchitecturePlane)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureValidationCell:
    plane: ChromatinArchitecturePlane
    operation_id: str
    receipt_count: int
    passed_receipt_count: int
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureValidationMatrix:
    fixture_id: str
    cells: tuple[ChromatinArchitectureValidationCell, ...]
    checks: tuple[ChromatinArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def validate_chromatin_architecture_matrix(
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
) -> ChromatinArchitectureValidationMatrix:
    by_operation = {
        item.operation_id: tuple(
            receipt for receipt in evaluation.receipts if receipt.operation_id == item.operation_id
        )
        for item in fixture.operations
    }
    cells = tuple(
        ChromatinArchitectureValidationCell(
            plane=plane,
            operation_id=operation.operation_id,
            receipt_count=len(receipts),
            passed_receipt_count=sum(item.passed for item in receipts),
            accepted=len(receipts) == 4
            and all(item.passed for item in receipts)
            and operation.plane in CHROMATIN_ARCHITECTURE_PLANES,
            detail=(
                f"{plane.value} matrix view observes {len(receipts)} receipts for "
                f"{operation.operation_id}"
            ),
            content_address=addressed(
                {
                    "plane": plane,
                    "operation_id": operation.operation_id,
                    "receipt_count": len(receipts),
                    "passed": sum(item.passed for item in receipts),
                },
                "chromatin-validation-cell",
            ),
        )
        for plane in CHROMATIN_ARCHITECTURE_PLANES
        for operation in fixture.operations
        for receipts in (by_operation[operation.operation_id],)
    )
    checks_data = (
        ("cell-cardinality", len(cells) == 80, len(cells), 80, "five planes × sixteen operations"),
        (
            "operation-coverage",
            all(cell.receipt_count == 4 for cell in cells),
            min(cell.receipt_count for cell in cells),
            4,
            "each operation has four receipts in every plane view",
        ),
        (
            "pass-coverage",
            all(cell.passed_receipt_count == 4 for cell in cells),
            min(cell.passed_receipt_count for cell in cells),
            4,
            "each matrix cell has four passing receipts",
        ),
        (
            "address-coverage",
            all(cell.content_address.startswith("sha256:") for cell in cells),
            True,
            True,
            "every validation cell is addressed",
        ),
        (
            "plane-coverage",
            {cell.plane for cell in cells} == set(CHROMATIN_ARCHITECTURE_PLANES),
            {cell.plane.value for cell in cells},
            {plane.value for plane in CHROMATIN_ARCHITECTURE_PLANES},
            "all evidence planes are represented",
        ),
    )
    checks = tuple(
        ChromatinArchitectureCheck(
            check_id,
            ChromatinArchitectureCheckKind.INVARIANT,
            passed,
            observed,
            required,
            detail,
            addressed(
                {
                    "check_id": check_id,
                    "passed": passed,
                    "observed": observed,
                    "required": required,
                },
                "chromatin-validation-check",
            ),
        )
        for check_id, passed, observed, required, detail in checks_data
    )
    body = {"fixture_id": fixture.fixture_id, "cells": cells, "checks": checks}
    return ChromatinArchitectureValidationMatrix(
        fixture.fixture_id,
        cells,
        checks,
        all(item.passed for item in checks) and all(item.accepted for item in cells),
        addressed(body, "chromatin-validation-matrix"),
    )


def chromatin_architecture_validation_summary(
    matrix: ChromatinArchitectureValidationMatrix,
) -> dict[str, Any]:
    return {
        "fixture_id": matrix.fixture_id,
        "cell_count": len(matrix.cells),
        "accepted": matrix.accepted,
        "content_address": matrix.content_address,
    }


__all__ = [
    "CHROMATIN_ARCHITECTURE_PLANES",
    "ChromatinArchitectureValidationCell",
    "ChromatinArchitectureValidationMatrix",
    "chromatin_architecture_validation_summary",
    "validate_chromatin_architecture_matrix",
]
