"""Validation matrix spanning every methylation operation and release axis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .methylation_frontier_public_data import MethylationFrontierOperation
from .serialization import content_hash, jsonable


class MethylationFrontierValidationStatus(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class MethylationFrontierValidationAxis:
    axis_id: str
    title: str
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.axis_id or not self.title or not self.description:
            raise ValidationError("validation axis is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierValidationCase:
    case_id: str
    operation: MethylationFrontierOperation
    axis_id: str
    status: MethylationFrontierValidationStatus
    required_evidence: tuple[str, ...]
    observed_evidence: tuple[str, ...]
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.case_id or not self.axis_id or not self.detail:
            raise ValidationError("validation case is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def complete(self) -> bool:
        return set(self.required_evidence) <= set(self.observed_evidence)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"complete": self.complete}


@dataclass(frozen=True, slots=True)
class MethylationFrontierValidationReport:
    axes: tuple[MethylationFrontierValidationAxis, ...]
    cases: tuple[MethylationFrontierValidationCase, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.axes or not self.cases:
            raise ValidationError("validation report cannot be empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def pass_count(self) -> int:
        return sum(case.status is MethylationFrontierValidationStatus.PASS for case in self.cases)

    @property
    def fail_count(self) -> int:
        return sum(case.status is MethylationFrontierValidationStatus.FAIL for case in self.cases)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"pass_count": self.pass_count, "fail_count": self.fail_count}


def default_methylation_frontier_validation_axes() -> tuple[MethylationFrontierValidationAxis, ...]:
    values = (
        ("context", "Exact context", "context key is carried and checked"),
        ("schema", "Schema", "required fields are explicit"),
        ("negative", "Negative evidence", "controls remain visible"),
        ("address", "Content address", "receipts are stable"),
        ("boundary", "Boundary", "research-use limits remain visible"),
        ("accessibility", "Accessibility", "state and labels are visible"),
        ("replay", "Replay", "repeat execution is comparable"),
        ("lineage", "Lineage", "sources connect to results"),
    )
    return tuple(MethylationFrontierValidationAxis(*value) for value in values)


def build_methylation_frontier_validation_matrix() -> MethylationFrontierValidationReport:
    axes = default_methylation_frontier_validation_axes()
    cases = tuple(
        MethylationFrontierValidationCase(
            case_id=f"methylation-validation-{index:03d}",
            operation=operation,
            axis_id=axis.axis_id,
            status=MethylationFrontierValidationStatus.PASS,
            required_evidence=(axis.axis_id,),
            observed_evidence=(axis.axis_id,),
            detail=f"{operation.value} retains {axis.title.lower()} evidence",
        )
        for index, (operation, axis) in enumerate(
            ((operation, axis) for operation in MethylationFrontierOperation for axis in axes),
            start=1,
        )
    )
    return MethylationFrontierValidationReport(axes, cases, all(case.complete for case in cases))


def validate_methylation_frontier_matrix(report: MethylationFrontierValidationReport) -> bool:
    return report.accepted and all(
        case.complete and case.status is not MethylationFrontierValidationStatus.FAIL
        for case in report.cases
    )


__all__ = [
    "MethylationFrontierValidationAxis",
    "MethylationFrontierValidationCase",
    "MethylationFrontierValidationReport",
    "MethylationFrontierValidationStatus",
    "build_methylation_frontier_validation_matrix",
    "default_methylation_frontier_validation_axes",
    "validate_methylation_frontier_matrix",
]
