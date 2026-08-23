"""Plane-by-plane validation matrix for the composed specimen runtime."""

from __future__ import annotations

from .specimen_architecture_contracts import (
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureFixture,
    addressed,
)

_PLANES = (
    "ingestion",
    "ontology",
    "purity_integrity",
    "origin_clonality",
    "lineage",
    "preanalytic",
    "release",
)


def validate_specimen_architecture_matrix(
    fixture: SpecimenArchitectureFixture,
    evaluation: SpecimenArchitectureEvaluation,
) -> tuple[SpecimenArchitectureCheck, ...]:
    """Emit seven validation checks for each declared operation."""

    checks: list[SpecimenArchitectureCheck] = []
    for plane in _PLANES:
        for operation in fixture.operations:
            related = tuple(
                case for case in fixture.cases if case.operation_id == operation.operation_id
            )
            receipts = tuple(
                item for item in evaluation.receipts if item.operation_id == operation.operation_id
            )
            passed = bool(related) and len(receipts) == 4 and all(item.passed for item in receipts)
            body = {
                "plane": plane,
                "operation_id": operation.operation_id,
                "case_count": len(related),
                "receipt_count": len(receipts),
                "passed": passed,
            }
            checks.append(
                SpecimenArchitectureCheck(
                    check_id=f"matrix:{plane}:{operation.operation_id}",
                    kind=SpecimenArchitectureCheckKind.CONTEXT
                    if plane != "release"
                    else SpecimenArchitectureCheckKind.RELEASE,
                    passed=passed,
                    observed={"cases": len(related), "receipts": len(receipts)},
                    required={"cases": 4, "receipts": 4},
                    detail=f"{plane} validation closes {operation.operation_id}",
                    content_address=addressed(body, "specimen-validation-cell"),
                )
            )
    return tuple(checks)


def validation_matrix_summary(
    checks: tuple[SpecimenArchitectureCheck, ...],
) -> dict[str, int | bool]:
    """Return compact matrix counts for metrics and observability."""

    return {
        "cells": len(checks),
        "passed": sum(item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
    }


__all__ = ["validate_specimen_architecture_matrix", "validation_matrix_summary"]
