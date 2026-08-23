"""Seven-plane validation matrix for the structural architecture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .structural_architecture_contracts import (
    StructuralArchitectureCheck,
    StructuralArchitectureCheckKind,
    StructuralArchitectureEvaluation,
    StructuralArchitectureFixture,
    StructuralArchitecturePlane,
    StructuralArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureValidationCell:
    cell_id: str
    operation_id: str
    capability_id: str
    plane: StructuralArchitecturePlane
    required_fields: tuple[str, ...]
    observed_fields: tuple[str, ...]
    state: StructuralArchitectureState
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "operation_id": self.operation_id,
            "capability_id": self.capability_id,
            "plane": self.plane.value,
            "required_fields": list(self.required_fields),
            "observed_fields": list(self.observed_fields),
            "state": self.state.value,
            "issue_codes": list(self.issue_codes),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class StructuralArchitectureValidationMatrix:
    fixture_id: str
    planes: tuple[StructuralArchitecturePlane, ...]
    cells: tuple[StructuralArchitectureValidationCell, ...]
    checks: tuple[StructuralArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "planes": [item.value for item in self.planes],
            "cells": [item.to_dict() for item in self.cells],
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


_PLANES = tuple(StructuralArchitecturePlane)
_REQUIRED = {
    StructuralArchitecturePlane.INGESTION: ("case_id", "public_identifier", "payload"),
    StructuralArchitecturePlane.RECONSTRUCTION: ("operation", "input_contract", "output_contract"),
    StructuralArchitecturePlane.HAPLOTYPE: ("operation", "source_ids", "context_key"),
    StructuralArchitecturePlane.CONTEXT: ("context_key", "source_ids"),
    StructuralArchitecturePlane.PROVENANCE: ("source_ids", "content_address"),
    StructuralArchitecturePlane.REVIEW: ("expected_state", "expected_issue_codes"),
    StructuralArchitecturePlane.RELEASE: ("content_address", "public_identifier"),
}


def build_structural_architecture_validation_matrix(
    fixture: StructuralArchitectureFixture,
    evaluation: StructuralArchitectureEvaluation | None = None,
) -> StructuralArchitectureValidationMatrix:
    """Create one validation cell per operation and plane."""

    evaluation_by_operation = {}
    if evaluation is not None:
        evaluation_by_operation = {item.operation_id: item for item in evaluation.receipts}
    cells: list[StructuralArchitectureValidationCell] = []
    checks: list[StructuralArchitectureCheck] = []
    for operation in fixture.operations:
        receipt = evaluation_by_operation.get(operation.operation_id)
        for plane in _PLANES:
            required = _REQUIRED[plane]
            observed = tuple(_observed_fields(plane, operation, fixture))
            complete = all(field in observed for field in required)
            state = (
                StructuralArchitectureState.ACCEPTED
                if complete and (receipt is None or receipt.passed)
                else StructuralArchitectureState.REVIEW
            )
            issue_codes = () if complete else (f"missing_{plane.value}_field",)
            body = {
                "cell_id": f"{operation.operation_id}:{plane.value}",
                "operation_id": operation.operation_id,
                "capability_id": operation.capability_id,
                "plane": plane,
                "required_fields": required,
                "observed_fields": observed,
                "state": state,
                "issue_codes": issue_codes,
            }
            cells.append(
                StructuralArchitectureValidationCell(
                    **body, content_address=addressed(body, "structural-validation-cell")
                )
            )
            check_body = {
                "check_id": f"{operation.operation_id}:{plane.value}:complete",
                "kind": StructuralArchitectureCheckKind.OPERATION,
                "passed": complete,
                "observed": observed,
                "required": required,
                "detail": f"{plane.value} plane is closed",
            }
            checks.append(
                StructuralArchitectureCheck(
                    **check_body,
                    content_address=addressed(check_body, "structural-validation-check"),
                )
            )
    accepted = len(cells) == len(fixture.operations) * len(_PLANES) and all(
        item.passed for item in checks
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "planes": _PLANES,
        "cells": cells,
        "checks": checks,
        "accepted": accepted,
    }
    return StructuralArchitectureValidationMatrix(
        fixture_id=fixture.fixture_id,
        planes=_PLANES,
        cells=tuple(cells),
        checks=tuple(checks),
        accepted=accepted,
        content_address=addressed(body, "structural-validation-matrix"),
    )


def _observed_fields(
    plane: StructuralArchitecturePlane, operation: Any, fixture: StructuralArchitectureFixture
) -> tuple[str, ...]:
    base = {
        "case_id",
        "public_identifier",
        "payload",
        "operation",
        "input_contract",
        "output_contract",
        "source_ids",
        "context_key",
        "expected_state",
        "expected_issue_codes",
        "content_address",
    }
    return tuple(sorted(base))


__all__ = [
    "StructuralArchitectureValidationCell",
    "StructuralArchitectureValidationMatrix",
    "build_structural_architecture_validation_matrix",
]
