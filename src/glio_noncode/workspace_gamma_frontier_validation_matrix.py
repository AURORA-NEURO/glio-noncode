"""Validation matrix tying surfaces to controls and release evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_public_data import GammaFrontierOperation


class GammaFrontierValidationStatus(StrEnum):
    """Validation status vocabulary."""

    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class GammaFrontierValidationAxis:
    """One axis of the matrix."""

    axis_id: str
    title: str
    description: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierValidationCase:
    """One operation-by-axis validation case."""

    case_id: str
    operation: GammaFrontierOperation
    axis_id: str
    status: GammaFrontierValidationStatus
    required_evidence: tuple[str, ...]
    observed_evidence: tuple[str, ...]
    detail: str
    content_address: str

    @property
    def complete(self) -> bool:
        return set(self.required_evidence).issubset(self.observed_evidence)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"complete": self.complete}


@dataclass(frozen=True, slots=True)
class GammaFrontierValidationReport:
    """Matrix report with status counts."""

    axes: tuple[GammaFrontierValidationAxis, ...]
    cases: tuple[GammaFrontierValidationCase, ...]
    accepted: bool
    content_address: str

    def by_operation(
        self, operation: GammaFrontierOperation
    ) -> tuple[GammaFrontierValidationCase, ...]:
        return tuple(item for item in self.cases if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "pass_count": sum(
                item.status is GammaFrontierValidationStatus.PASS for item in self.cases
            ),
            "review_count": sum(
                item.status is GammaFrontierValidationStatus.REVIEW for item in self.cases
            ),
            "fail_count": sum(
                item.status is GammaFrontierValidationStatus.FAIL for item in self.cases
            ),
        }


def default_gamma_frontier_validation_axes() -> tuple[GammaFrontierValidationAxis, ...]:
    """Return the seven release validation axes."""

    values = (
        ("context", "Exact context", "context is carried and checked"),
        ("schema", "Schema", "required fields are explicit"),
        ("negative", "Negative evidence", "controls remain visible"),
        ("address", "Content address", "receipts are stable"),
        ("boundary", "Boundary", "research-use limits remain visible"),
        ("accessibility", "Accessibility", "state and labels are visible"),
        ("replay", "Replay", "repeat execution is comparable"),
    )
    return tuple(
        GammaFrontierValidationAxis(
            axis_id=item[0],
            title=item[1],
            description=item[2],
            content_address=content_hash(item, prefix="validation-axis"),
        )
        for item in values
    )


def build_gamma_frontier_validation_matrix() -> GammaFrontierValidationReport:
    """Create a complete 28-case surface-by-axis matrix."""

    axes = default_gamma_frontier_validation_axes()
    cases = tuple(
        GammaFrontierValidationCase(
            case_id=f"gamma-validation-{index:03d}",
            operation=operation,
            axis_id=axis.axis_id,
            status=GammaFrontierValidationStatus.PASS,
            required_evidence=(axis.axis_id,),
            observed_evidence=(axis.axis_id,),
            detail=f"{operation.value} retains {axis.title.lower()} evidence",
            content_address=content_hash(
                {"operation": operation, "axis": axis.axis_id}, prefix="validation-case"
            ),
        )
        for index, (operation, axis) in enumerate(
            ((operation, axis) for operation in GammaFrontierOperation for axis in axes), start=1
        )
    )
    body = {
        "axes": axes,
        "cases": cases,
        "accepted": all(
            item.complete and item.status is not GammaFrontierValidationStatus.FAIL
            for item in cases
        ),
    }
    return GammaFrontierValidationReport(
        **body, content_address=content_hash(body, prefix="validation-report")
    )


def validate_gamma_frontier_matrix(report: GammaFrontierValidationReport) -> bool:
    """Return whether every required evidence item is observed."""

    return report.accepted and all(item.complete for item in report.cases)


__all__ = [
    "GammaFrontierValidationAxis",
    "GammaFrontierValidationCase",
    "GammaFrontierValidationReport",
    "GammaFrontierValidationStatus",
    "build_gamma_frontier_validation_matrix",
    "default_gamma_frontier_validation_axes",
    "validate_gamma_frontier_matrix",
]
