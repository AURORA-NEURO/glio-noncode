"""Validation matrix for cross-surface C05-C08 behavior.

The scenario matrix describes input dimensions. This module binds those
dimensions to observed execution receipts and exposes a second report that can
be used by a test harness, release dashboard, or future review client.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation, BetaFrontierExecution
from .workspace_beta_frontier_public_data import BetaFrontierOperation


class BetaFrontierValidationStatus(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class BetaFrontierValidationAxis:
    axis_id: str
    label: str
    values: tuple[str, ...]
    interpretation: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.axis_id, "axis_id")
        require_non_empty(self.label, "label")
        require_non_empty(self.interpretation, "interpretation")
        if not self.values:
            raise ValueError("beta validation axis requires values")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierValidationCase:
    case_id: str
    record_id: str | None
    operation: BetaFrontierOperation | None
    axis_id: str
    axis_value: str
    status: BetaFrontierValidationStatus
    observed_state: str
    issue_codes: tuple[str, ...]
    evidence_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("case_id", "axis_id", "axis_value", "observed_state", "evidence_address", "detail", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierValidationReport:
    fixture_id: str
    axes: tuple[BetaFrontierValidationAxis, ...]
    cases: tuple[BetaFrontierValidationCase, ...]
    accepted: bool
    pass_count: int
    review_count: int
    hold_count: int
    failed_case_ids: tuple[str, ...]
    content_address: str

    def for_axis(self, axis_id: str) -> tuple[BetaFrontierValidationCase, ...]:
        return tuple(item for item in self.cases if item.axis_id == axis_id)

    def for_operation(self, operation: BetaFrontierOperation) -> tuple[BetaFrontierValidationCase, ...]:
        return tuple(item for item in self.cases if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _axis(axis_id: str, label: str, values: tuple[str, ...], interpretation: str) -> BetaFrontierValidationAxis:
    body = {"axis_id": axis_id, "label": label, "values": values, "interpretation": interpretation}
    return BetaFrontierValidationAxis(**body, content_address=content_hash(body))


def default_beta_frontier_validation_axes() -> tuple[BetaFrontierValidationAxis, ...]:
    """Return the eight dimensions used to organize cross-surface checks."""

    values = (
        ("context", "Context qualification", ("exact", "foreign"), "exact context is required"),
        ("state", "State preservation", ("supported", "partial", "absent", "abstained", "contradictory"), "states remain distinct"),
        ("receipts", "Receipt retention", ("present", "missing"), "source and output receipts remain visible"),
        ("alternatives", "Alternative paths", ("single", "multiple"), "alternative evidence is retained"),
        ("reconciliation", "Reconciliation", ("matched", "residual"), "declared values are compared to visible components"),
        ("pagination", "Pagination", ("full", "paged"), "total match count survives page selection"),
        ("bounds", "Output bounds", ("within", "boundary"), "node, edge, and page limits are explicit"),
        ("accessibility", "Interaction metadata", ("labeled", "review"), "labels and review notes are available"),
    )
    return tuple(_axis(*item) for item in values)


def _status(execution: BetaFrontierExecution, axis_id: str) -> BetaFrontierValidationStatus:
    if execution.state in {"invalid", "contradictory", "out_of_domain"}:
        return BetaFrontierValidationStatus.HOLD
    if axis_id in {"state", "reconciliation", "pagination", "accessibility"} and execution.state in {"partial", "incomplete", "absent", "abstained"}:
        return BetaFrontierValidationStatus.REVIEW
    return BetaFrontierValidationStatus.PASS


def _case(index: int, execution: BetaFrontierExecution, axis: BetaFrontierValidationAxis, axis_value: str) -> BetaFrontierValidationCase:
    status = _status(execution, axis.axis_id)
    detail = f"{axis.label}={axis_value} observed for {execution.record_id}"
    body = {"case_id": f"validation-case-{index:03d}", "record_id": execution.record_id, "operation": execution.operation, "axis_id": axis.axis_id, "axis_value": axis_value, "status": status, "observed_state": execution.state, "issue_codes": execution.issue_codes, "evidence_address": execution.content_address, "detail": detail}
    return BetaFrontierValidationCase(**body, content_address=content_hash(body))


def build_beta_frontier_validation_matrix(evaluation: BetaFrontierEvaluation) -> BetaFrontierValidationReport:
    """Bind each execution to every validation axis it can exercise."""

    axes = default_beta_frontier_validation_axes()
    cases: list[BetaFrontierValidationCase] = []
    index = 1
    for execution in evaluation.executions:
        for axis in axes:
            if axis.axis_id == "context":
                value = "foreign" if "context_mismatch" in execution.issue_codes else "exact"
            elif axis.axis_id == "receipts":
                value = "present" if execution.content_address.startswith("sha256:") else "missing"
            elif axis.axis_id == "alternatives":
                alternatives = execution.output.get("alternative_edge_ids", ())
                value = "multiple" if len(alternatives) > 1 else "single"
            elif axis.axis_id == "reconciliation":
                value = "residual" if "unreconciled_components" in execution.issue_codes else "matched"
            elif axis.axis_id == "pagination":
                value = "paged" if "pagination_applied" in execution.issue_codes else "full"
            elif axis.axis_id == "bounds":
                value = "within" if execution.state != "invalid" else "boundary"
            elif axis.axis_id == "accessibility":
                value = "review" if execution.role.value == "control" else "labeled"
            else:
                value = execution.state
            cases.append(_case(index, execution, axis, value))
            index += 1
    failed = tuple(item.case_id for item in cases if not item.evidence_address.startswith("sha256:"))
    pass_count = sum(item.status is BetaFrontierValidationStatus.PASS for item in cases)
    review_count = sum(item.status is BetaFrontierValidationStatus.REVIEW for item in cases)
    hold_count = sum(item.status is BetaFrontierValidationStatus.HOLD for item in cases)
    body = {"fixture_id": evaluation.fixture_id, "axes": axes, "cases": tuple(cases), "accepted": not failed, "pass_count": pass_count, "review_count": review_count, "hold_count": hold_count, "failed_case_ids": failed}
    return BetaFrontierValidationReport(**body, content_address=content_hash(body))


def validate_beta_frontier_matrix(evaluation: BetaFrontierEvaluation) -> BetaFrontierValidationReport:
    """Alias used by test and release clients."""

    return build_beta_frontier_validation_matrix(evaluation)


__all__ = ["BetaFrontierValidationAxis", "BetaFrontierValidationCase", "BetaFrontierValidationReport", "BetaFrontierValidationStatus", "build_beta_frontier_validation_matrix", "default_beta_frontier_validation_axes", "validate_beta_frontier_matrix"]
