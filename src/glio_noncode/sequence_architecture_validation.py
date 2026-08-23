"""Five-plane by sixteen-operation D06 validation matrix."""

from __future__ import annotations

from .sequence_architecture_contracts import (
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    SequenceArchitecturePlane,
    addressed,
)

SEQUENCE_ARCHITECTURE_PLANES = tuple(item.value for item in SequenceArchitecturePlane)


def validate_sequence_architecture_matrix(
    fixture: SequenceArchitectureFixture, evaluation: SequenceArchitectureEvaluation
) -> tuple[SequenceArchitectureCheck, ...]:
    checks: list[SequenceArchitectureCheck] = []
    for plane in SequenceArchitecturePlane:
        for operation in fixture.operations:
            receipts = tuple(
                item for item in evaluation.receipts if item.operation_id == operation.operation_id
            )
            passed = (
                len(receipts) == 4
                and all(item.passed for item in receipts)
                and operation.plane in SequenceArchitecturePlane
            )
            checks.append(
                _check(
                    f"{plane.value}-{operation.operation_id}",
                    passed,
                    {
                        "plane": plane.value,
                        "operation": operation.operation_id,
                        "receipt_count": len(receipts),
                    },
                    {"receipt_count": 4, "operation_declared": True},
                    "plane closure checks all four cases for every operation",
                )
            )
    return tuple(checks)


def sequence_validation_summary(
    checks: tuple[SequenceArchitectureCheck, ...],
) -> dict[str, int | bool]:
    return {
        "cell_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
    }


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.OPERATION,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.OPERATION,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-validation-check"),
    )


__all__ = [
    "SEQUENCE_ARCHITECTURE_PLANES",
    "sequence_validation_summary",
    "validate_sequence_architecture_matrix",
]
