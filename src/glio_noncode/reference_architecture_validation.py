"""Five-plane by sixteen-operation validation matrix for D04."""

from __future__ import annotations

from .reference_architecture_contracts import (
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureFixture,
    addressed,
)

REFERENCE_ARCHITECTURE_PLANES = ("ingestion", "coordinate", "annotation", "governance", "release")


def validate_reference_architecture_matrix(
    fixture: ReferenceArchitectureFixture, evaluation: ReferenceArchitectureEvaluation
) -> tuple[ReferenceArchitectureCheck, ...]:
    """Close 80 matrix cells from operation and receipt cardinality."""

    checks: list[ReferenceArchitectureCheck] = []
    for plane in REFERENCE_ARCHITECTURE_PLANES:
        for operation in fixture.operations:
            cases = tuple(
                item for item in fixture.cases if item.operation_id == operation.operation_id
            )
            receipts = tuple(
                item for item in evaluation.receipts if item.operation_id == operation.operation_id
            )
            passed = (
                len(cases) == 4 and len(receipts) == 4 and all(item.passed for item in receipts)
            )
            body = {
                "plane": plane,
                "operation_id": operation.operation_id,
                "case_count": len(cases),
                "receipt_count": len(receipts),
                "passed": passed,
            }
            checks.append(
                ReferenceArchitectureCheck(
                    f"matrix:{plane}:{operation.operation_id}",
                    ReferenceArchitectureCheckKind.RELEASE
                    if plane == "release"
                    else ReferenceArchitectureCheckKind.CONTEXT,
                    passed,
                    {"cases": len(cases), "receipts": len(receipts)},
                    {"cases": 4, "receipts": 4},
                    f"{plane} validation closes {operation.operation_id}",
                    addressed(body, "reference-validation-cell"),
                )
            )
    return tuple(checks)


def reference_validation_summary(
    checks: tuple[ReferenceArchitectureCheck, ...],
) -> dict[str, int | bool]:
    """Return bounded matrix counters."""

    return {
        "cells": len(checks),
        "passed": sum(item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
    }


__all__ = [
    "REFERENCE_ARCHITECTURE_PLANES",
    "reference_validation_summary",
    "validate_reference_architecture_matrix",
]
