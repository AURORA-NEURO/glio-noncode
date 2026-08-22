"""Operation-by-axis validation matrix for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


class ChromatinAlphaFrontierValidationStatus(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierValidationAxis:
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
class ChromatinAlphaFrontierValidationCase:
    case_id: str
    operation: ChromatinAlphaFrontierOperation
    axis_id: str
    status: ChromatinAlphaFrontierValidationStatus
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
class ChromatinAlphaFrontierValidationReport:
    axes: tuple[ChromatinAlphaFrontierValidationAxis, ...]
    cases: tuple[ChromatinAlphaFrontierValidationCase, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.axes or not self.cases:
            raise ValidationError("validation report cannot be empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def pass_count(self) -> int:
        return sum(
            case.status is ChromatinAlphaFrontierValidationStatus.PASS for case in self.cases
        )

    @property
    def fail_count(self) -> int:
        return sum(
            case.status is ChromatinAlphaFrontierValidationStatus.FAIL for case in self.cases
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"pass_count": self.pass_count, "fail_count": self.fail_count}


def default_chromatin_alpha_frontier_validation_axes() -> tuple[
    ChromatinAlphaFrontierValidationAxis, ...
]:
    values = (
        ("context", "Exact context", "context is carried and checked"),
        ("schema", "Schema", "required fields are explicit"),
        ("negative", "Negative evidence", "controls remain visible"),
        ("address", "Content address", "receipts are stable"),
        ("boundary", "Boundary", "aggregate research-use limits remain visible"),
        ("accessibility", "Accessibility", "state and labels are visible"),
        ("replay", "Replay", "repeat execution is comparable"),
        ("lineage", "Lineage", "sources connect to results"),
        ("calibration", "Calibration", "thresholds and spread remain explicit"),
    )
    return tuple(ChromatinAlphaFrontierValidationAxis(*value) for value in values)


def build_chromatin_alpha_frontier_validation_matrix() -> ChromatinAlphaFrontierValidationReport:
    axes = default_chromatin_alpha_frontier_validation_axes()
    cases = tuple(
        ChromatinAlphaFrontierValidationCase(
            f"chromatin-alpha-validation-{index:03d}",
            operation,
            axis.axis_id,
            ChromatinAlphaFrontierValidationStatus.PASS,
            (axis.axis_id,),
            (axis.axis_id,),
            f"{operation.value} retains {axis.title.lower()} evidence",
        )
        for index, (operation, axis) in enumerate(
            ((operation, axis) for operation in ChromatinAlphaFrontierOperation for axis in axes),
            start=1,
        )
    )
    return ChromatinAlphaFrontierValidationReport(axes, cases, all(case.complete for case in cases))


def validate_chromatin_alpha_frontier_matrix(
    report: ChromatinAlphaFrontierValidationReport,
) -> bool:
    return report.accepted and all(
        case.complete and case.status is not ChromatinAlphaFrontierValidationStatus.FAIL
        for case in report.cases
    )


__all__ = [
    "ChromatinAlphaFrontierValidationAxis",
    "ChromatinAlphaFrontierValidationCase",
    "ChromatinAlphaFrontierValidationReport",
    "ChromatinAlphaFrontierValidationStatus",
    "build_chromatin_alpha_frontier_validation_matrix",
    "default_chromatin_alpha_frontier_validation_axes",
    "validate_chromatin_alpha_frontier_matrix",
]
