"""Evidence-plane matrix for the validation-beta planning operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .validation_beta_frontier_fixture_eval import (
    ValidationBetaFrontierEvaluation,
    evaluate_validation_beta_frontier_fixture,
)
from .validation_beta_frontier_public_data import (
    ValidationBetaFrontierFixture,
    ValidationBetaFrontierOperation,
    ValidationBetaFrontierRole,
    default_validation_beta_frontier_fixture,
)


VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES = (
    "public-data",
    "adapter",
    "contract",
    "execution",
    "quality",
    "release",
)

_REQUIRED_CHECKS = {
    ValidationBetaFrontierOperation.CRISPR_DESIGN: ("target-context", "mode-coverage", "guide-blockers"),
    ValidationBetaFrontierOperation.BASE_EDITING: ("edit-window", "base-pair", "reference-context"),
    ValidationBetaFrontierOperation.PRIME_EDITING: ("pbs", "rtt", "flank"),
    ValidationBetaFrontierOperation.ALLELE_REPORTER: ("allele-pair", "reporter-context", "replicate-plan"),
    ValidationBetaFrontierOperation.MODEL_ELIGIBILITY: ("context-exactness", "model-attributes", "subject-boundary"),
    ValidationBetaFrontierOperation.GUIDE_OLIGO: ("oligo-sequence", "gc-band", "manufacturing-boundary"),
    ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION: ("control-balance", "randomization", "seed-receipt"),
    ValidationBetaFrontierOperation.POWER_REPLICATION: ("power-inputs", "replication", "shortfall-boundary"),
}


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierValidationCell:
    """One record mapped across all required implementation planes."""

    cell_id: str
    record_id: str
    operation: ValidationBetaFrontierOperation
    role: ValidationBetaFrontierRole
    expected_disposition: str
    observed_disposition: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    evidence_planes: tuple[str, ...]
    required_checks: tuple[str, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("cell_id", "record_id", "expected_disposition", "observed_disposition", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.evidence_planes:
            raise ValueError("validation matrix cells require evidence planes")
        if not self.required_checks:
            raise ValueError("validation matrix cells require named checks")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("validation matrix cell address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierValidationMatrix:
    """Complete record-to-plane matrix with explicit failed-cell accounting."""

    fixture_id: str
    axes: tuple[str, ...]
    cells: tuple[ValidationBetaFrontierValidationCell, ...]
    accepted: bool
    failed_cell_ids: tuple[str, ...]
    content_address: str

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    @property
    def operation_count(self) -> int:
        return len({item.operation for item in self.cells})

    def by_operation(self, operation: ValidationBetaFrontierOperation | str) -> tuple[ValidationBetaFrontierValidationCell, ...]:
        selected = operation.value if isinstance(operation, ValidationBetaFrontierOperation) else str(operation)
        return tuple(item for item in self.cells if item.operation.value == selected)

    def by_plane(self, plane: str) -> tuple[ValidationBetaFrontierValidationCell, ...]:
        require_non_empty(plane, "plane")
        return tuple(item for item in self.cells if plane in item.evidence_planes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "cell_count": self.cell_count,
            "operation_count": self.operation_count,
        }


def _cell(
    record: Any,
    row: Any,
) -> ValidationBetaFrontierValidationCell:
    operation = record.operation
    cell_id = f"matrix-{record.record_id.lower()}"
    expected = str(record.expected_state)
    observed = str(row.observed_state)
    planes = VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES
    checks = _REQUIRED_CHECKS[operation]
    body = {
        "cell_id": cell_id,
        "record_id": record.record_id,
        "operation": operation,
        "role": record.role,
        "expected_disposition": expected,
        "observed_disposition": observed,
        "expected_issue_codes": tuple(record.expected_issue_codes),
        "observed_issue_codes": tuple(row.observed_issue_codes),
        "evidence_planes": planes,
        "required_checks": checks,
        "accepted": bool(row.accepted and expected == observed),
    }
    return ValidationBetaFrontierValidationCell(**body, content_address=content_hash(body))


def build_validation_beta_frontier_validation_matrix(
    fixture: ValidationBetaFrontierFixture | None = None,
    evaluation: ValidationBetaFrontierEvaluation | None = None,
) -> ValidationBetaFrontierValidationMatrix:
    """Build one complete matrix cell for each evaluated fixture record."""

    value = fixture or default_validation_beta_frontier_fixture()
    report = evaluation or evaluate_validation_beta_frontier_fixture(value)
    rows = {item.record_id: item for item in report.rows}
    cells: list[ValidationBetaFrontierValidationCell] = []
    for record in value.records:
        row = rows.get(record.record_id)
        if row is None:
            raise ValueError(f"validation matrix missing evaluation row: {record.record_id}")
        cells.append(_cell(record, row))
    failed = tuple(item.cell_id for item in cells if not item.accepted)
    body = {"fixture_id": value.fixture_id, "axes": VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES, "cells": tuple(cells), "failed": failed}
    return ValidationBetaFrontierValidationMatrix(
        fixture_id=value.fixture_id,
        axes=VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES,
        cells=tuple(cells),
        accepted=not failed,
        failed_cell_ids=failed,
        content_address=content_hash(body),
    )


def validate_validation_beta_frontier_matrix(matrix: ValidationBetaFrontierValidationMatrix) -> bool:
    """Check matrix conservation, plane closure, and operation balance."""

    if not matrix.accepted or matrix.failed_cell_ids:
        return False
    if matrix.axes != VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES or len(matrix.cells) != 32:
        return False
    if len({item.record_id for item in matrix.cells}) != 32:
        return False
    if set(item.operation for item in matrix.cells) != set(ValidationBetaFrontierOperation):
        return False
    for operation in ValidationBetaFrontierOperation:
        cells = matrix.by_operation(operation)
        if len(cells) != 4 or any(item.required_checks != _REQUIRED_CHECKS[operation] for item in cells):
            return False
        if any(item.evidence_planes != VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES for item in cells):
            return False
    return all(item.accepted and item.content_address.startswith("sha256:") for item in matrix.cells)


def validation_beta_frontier_matrix_summary(matrix: ValidationBetaFrontierValidationMatrix | None = None) -> dict[str, Any]:
    value = matrix or build_validation_beta_frontier_validation_matrix()
    return {
        "accepted": value.accepted and validate_validation_beta_frontier_matrix(value),
        "fixture_id": value.fixture_id,
        "cell_count": value.cell_count,
        "operation_count": value.operation_count,
        "axis_count": len(value.axes),
        "failed_cell_ids": value.failed_cell_ids,
        "content_address": value.content_address,
    }


__all__ = [
    "VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES",
    "ValidationBetaFrontierValidationCell",
    "ValidationBetaFrontierValidationMatrix",
    "build_validation_beta_frontier_validation_matrix",
    "validate_validation_beta_frontier_matrix",
    "validation_beta_frontier_matrix_summary",
]
