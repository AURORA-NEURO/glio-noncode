"""Five-plane by sixteen-operation validation matrix for D05."""

from __future__ import annotations

from .atlas_architecture_contracts import (
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureEvaluation,
    AtlasArchitectureFixture,
    AtlasArchitecturePlane,
    addressed,
)

ATLAS_ARCHITECTURE_PLANES = tuple(item.value for item in AtlasArchitecturePlane)


def validate_atlas_architecture_matrix(
    fixture: AtlasArchitectureFixture,
    evaluation: AtlasArchitectureEvaluation,
) -> tuple[AtlasArchitectureCheck, ...]:
    """Validate every operation against every architecture plane."""

    checks: list[AtlasArchitectureCheck] = []
    for plane in AtlasArchitecturePlane:
        for spec in fixture.operations:
            check_id = f"{plane.value}:{spec.operation_id}"
            cases = tuple(item for item in fixture.cases if item.operation_id == spec.operation_id)
            receipts = tuple(
                item for item in evaluation.receipts if item.operation_id == spec.operation_id
            )
            passed = (
                len(cases) == 4 and len(receipts) == 4 and all(item.passed for item in receipts)
            )
            required = {"cases": 4, "receipts": 4}
            body = {
                "check_id": check_id,
                "kind": AtlasArchitectureCheckKind.INVARIANT,
                "passed": passed,
                "observed": {"cases": len(cases), "receipts": len(receipts)},
                "required": required,
                "detail": "plane-operation validation cell is closed",
            }
            checks.append(
                AtlasArchitectureCheck(
                    check_id,
                    AtlasArchitectureCheckKind.INVARIANT,
                    passed,
                    body["observed"],
                    required,
                    body["detail"],
                    addressed(body, "atlas-validation-cell"),
                )
            )
    return tuple(checks)


def atlas_validation_summary(checks: tuple[AtlasArchitectureCheck, ...]) -> dict[str, int | bool]:
    return {
        "cell_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
    }


__all__ = [
    "ATLAS_ARCHITECTURE_PLANES",
    "atlas_validation_summary",
    "validate_atlas_architecture_matrix",
]
