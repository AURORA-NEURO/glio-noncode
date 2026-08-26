"""Deterministic comparisons between two verified execution metrics views.

An execution release diff should answer more than whether bytes changed.  This
module compares the operational metrics projection at two points in time and
preserves both aggregate deltas and row-level explanations.  Positive deltas
mean the right-hand release has more of the measured quantity; completion and
check coverage use integer basis points; missing durations remain ``None``
rather than being silently treated as zero.

The comparison is descriptive.  It does not rank scientific hypotheses,
assign a reviewer, infer a cause, or convert operational completion into a
scientific conclusion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_execution_metrics import (
    ReviewWorkspaceExecutionActionMetrics,
    ReviewWorkspaceExecutionLaneMetrics,
    ReviewWorkspaceExecutionMetrics,
)
from .serialization import content_hash, jsonable


REVIEW_WORKSPACE_EXECUTION_METRICS_DIFF_VERSION = "review-workspace-execution-metrics-diff-v1"
REVIEW_WORKSPACE_EXECUTION_METRICS_DIFF_SCHEMA_VERSION = (
    "review-workspace-execution-metrics-diff-schema-v1"
)

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact",
        "contact_name",
        "credential",
        "credential_value",
        "email",
        "generated_by",
        "individual",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant",
        "participant_id",
        "patient",
        "patient_id",
        "phone",
        "programming_language",
        "produced_by",
        "sample",
        "sample_id",
        "secret",
        "secret_key",
        "subject",
        "subject_id",
        "token",
    }
)


def _text(value: Any, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be blank")
    return normalized


def _delta(left: int, right: int) -> int:
    return int(right) - int(left)


def _optional_delta(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return int(right) - int(left)


def _count_deltas(
    left: Mapping[str, int],
    right: Mapping[str, int],
) -> dict[str, int]:
    keys = sorted(set(left) | set(right))
    return {key: _delta(int(left.get(key, 0)), int(right.get(key, 0))) for key in keys}


def _address(body: Any, prefix: str) -> str:
    return content_hash(body, prefix=prefix)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionActionMetricsDiff:
    """Operational metric changes for one action identifier."""

    action_id: str
    left_status: str | None
    right_status: str | None
    left_address: str | None
    right_address: str | None
    event_count_delta: int
    execution_seconds_delta: int | None
    completion_check_coverage_basis_points_delta: int
    reopened_count_delta: int
    block_count_delta: int
    changed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionLaneMetricsDiff:
    """Operational metric changes for one plan lane."""

    lane: str
    left_action_count: int
    right_action_count: int
    action_count_delta: int
    event_count_delta: int
    estimate_units_delta: int
    completed_estimate_units_delta: int
    completion_basis_points_delta: int
    blocked_action_count_delta: int
    dependency_wait_action_count_delta: int
    mean_execution_seconds_delta: int | None
    changed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionMetricsDiff:
    """Complete aggregate and row-level operational metrics comparison."""

    left_execution_id: str
    right_execution_id: str
    left_execution_address: str
    right_execution_address: str
    left_plan_address: str
    right_plan_address: str
    left_metrics_address: str
    right_metrics_address: str
    metrics_changed: bool
    event_count_delta: int
    action_count_delta: int
    estimate_units_delta: int
    completed_estimate_units_delta: int
    completion_basis_points_delta: int
    check_coverage_basis_points_delta: int
    required_check_count_delta: int
    passed_required_check_count_delta: int
    dependency_wait_count_delta: int
    active_span_seconds_delta: int | None
    reopen_count_delta: int
    block_count_delta: int
    skip_count_delta: int
    critical_path_estimate_units_delta: int
    critical_path_completed_units_delta: int
    status_count_deltas: Mapping[str, int]
    event_kind_count_deltas: Mapping[str, int]
    action_diffs: tuple[ReviewWorkspaceExecutionActionMetricsDiff, ...]
    lane_diffs: tuple[ReviewWorkspaceExecutionLaneMetricsDiff, ...]
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_version": REVIEW_WORKSPACE_EXECUTION_METRICS_DIFF_VERSION,
            "left_execution_id": self.left_execution_id,
            "right_execution_id": self.right_execution_id,
            "left_execution_address": self.left_execution_address,
            "right_execution_address": self.right_execution_address,
            "left_plan_address": self.left_plan_address,
            "right_plan_address": self.right_plan_address,
            "left_metrics_address": self.left_metrics_address,
            "right_metrics_address": self.right_metrics_address,
            "metrics_changed": self.metrics_changed,
            "event_count_delta": self.event_count_delta,
            "action_count_delta": self.action_count_delta,
            "estimate_units_delta": self.estimate_units_delta,
            "completed_estimate_units_delta": self.completed_estimate_units_delta,
            "completion_basis_points_delta": self.completion_basis_points_delta,
            "check_coverage_basis_points_delta": self.check_coverage_basis_points_delta,
            "required_check_count_delta": self.required_check_count_delta,
            "passed_required_check_count_delta": self.passed_required_check_count_delta,
            "dependency_wait_count_delta": self.dependency_wait_count_delta,
            "active_span_seconds_delta": self.active_span_seconds_delta,
            "reopen_count_delta": self.reopen_count_delta,
            "block_count_delta": self.block_count_delta,
            "skip_count_delta": self.skip_count_delta,
            "critical_path_estimate_units_delta": self.critical_path_estimate_units_delta,
            "critical_path_completed_units_delta": self.critical_path_completed_units_delta,
            "status_count_deltas": dict(self.status_count_deltas),
            "event_kind_count_deltas": dict(self.event_kind_count_deltas),
            "action_diffs": [item.to_dict() for item in self.action_diffs],
            "lane_diffs": [item.to_dict() for item in self.lane_diffs],
            "accepted": self.accepted,
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


def _action_map(
    rows: tuple[ReviewWorkspaceExecutionActionMetrics, ...],
) -> dict[str, ReviewWorkspaceExecutionActionMetrics]:
    result: dict[str, ReviewWorkspaceExecutionActionMetrics] = {}
    for row in rows:
        if row.action_id in result:
            raise ValidationError(f"duplicate action metrics identifier: {row.action_id}")
        result[row.action_id] = row
    return result


def _lane_map(
    rows: tuple[ReviewWorkspaceExecutionLaneMetrics, ...],
) -> dict[str, ReviewWorkspaceExecutionLaneMetrics]:
    result: dict[str, ReviewWorkspaceExecutionLaneMetrics] = {}
    for row in rows:
        if row.lane in result:
            raise ValidationError(f"duplicate lane metrics identifier: {row.lane}")
        result[row.lane] = row
    return result


def _action_diff(
    action_id: str,
    left: ReviewWorkspaceExecutionActionMetrics | None,
    right: ReviewWorkspaceExecutionActionMetrics | None,
) -> ReviewWorkspaceExecutionActionMetricsDiff:
    left_status = None if left is None else left.status
    right_status = None if right is None else right.status
    left_address = None if left is None else left.content_address
    right_address = None if right is None else right.content_address
    body = {
        "action_id": action_id,
        "left_status": left_status,
        "right_status": right_status,
        "left_address": left_address,
        "right_address": right_address,
        "event_count_delta": _delta(0 if left is None else left.event_count, 0 if right is None else right.event_count),
        "execution_seconds_delta": _optional_delta(
            None if left is None else left.execution_seconds,
            None if right is None else right.execution_seconds,
        ),
        "completion_check_coverage_basis_points_delta": _delta(
            0 if left is None else left.completion_check_coverage_basis_points,
            0 if right is None else right.completion_check_coverage_basis_points,
        ),
        "reopened_count_delta": _delta(0 if left is None else left.reopen_count, 0 if right is None else right.reopen_count),
        "block_count_delta": _delta(0 if left is None else left.block_count, 0 if right is None else right.block_count),
    }
    body["changed"] = any(
        (
            left_address != right_address,
            body["event_count_delta"] != 0,
            body["execution_seconds_delta"] not in {None, 0},
            body["completion_check_coverage_basis_points_delta"] != 0,
            body["reopened_count_delta"] != 0,
            body["block_count_delta"] != 0,
        )
    )
    return ReviewWorkspaceExecutionActionMetricsDiff(
        **body,
        content_address=_address(body, "review-workspace-execution-action-metrics-diff"),
    )


def _lane_diff(
    lane: str,
    left: ReviewWorkspaceExecutionLaneMetrics | None,
    right: ReviewWorkspaceExecutionLaneMetrics | None,
) -> ReviewWorkspaceExecutionLaneMetricsDiff:
    body = {
        "lane": lane,
        "left_action_count": 0 if left is None else left.action_count,
        "right_action_count": 0 if right is None else right.action_count,
        "action_count_delta": _delta(0 if left is None else left.action_count, 0 if right is None else right.action_count),
        "event_count_delta": _delta(0 if left is None else left.event_count, 0 if right is None else right.event_count),
        "estimate_units_delta": _delta(0 if left is None else left.estimate_units, 0 if right is None else right.estimate_units),
        "completed_estimate_units_delta": _delta(
            0 if left is None else left.completed_estimate_units,
            0 if right is None else right.completed_estimate_units,
        ),
        "completion_basis_points_delta": _delta(
            0 if left is None else left.completion_basis_points,
            0 if right is None else right.completion_basis_points,
        ),
        "blocked_action_count_delta": _delta(
            0 if left is None else len(left.blocked_action_ids),
            0 if right is None else len(right.blocked_action_ids),
        ),
        "dependency_wait_action_count_delta": _delta(
            0 if left is None else len(left.dependency_wait_action_ids),
            0 if right is None else len(right.dependency_wait_action_ids),
        ),
        "mean_execution_seconds_delta": _optional_delta(
            None if left is None else left.mean_execution_seconds,
            None if right is None else right.mean_execution_seconds,
        ),
    }
    body["changed"] = any(
        value not in {0, None}
        for key, value in body.items()
        if key not in {"lane", "left_action_count", "right_action_count"}
    )
    return ReviewWorkspaceExecutionLaneMetricsDiff(
        **body,
        content_address=_address(body, "review-workspace-execution-lane-metrics-diff"),
    )


def diff_review_workspace_execution_metrics(
    left: ReviewWorkspaceExecutionMetrics,
    right: ReviewWorkspaceExecutionMetrics,
) -> ReviewWorkspaceExecutionMetricsDiff:
    """Compare two typed operational metrics projections."""

    if not isinstance(left, ReviewWorkspaceExecutionMetrics) or not isinstance(
        right, ReviewWorkspaceExecutionMetrics
    ):
        raise ValidationError("metrics diff requires two typed metrics projections")
    left_actions = _action_map(left.action_metrics)
    right_actions = _action_map(right.action_metrics)
    action_diffs = tuple(
        _action_diff(action_id, left_actions.get(action_id), right_actions.get(action_id))
        for action_id in sorted(set(left_actions) | set(right_actions))
    )
    left_lanes = _lane_map(left.lane_metrics)
    right_lanes = _lane_map(right.lane_metrics)
    lane_diffs = tuple(
        _lane_diff(lane, left_lanes.get(lane), right_lanes.get(lane))
        for lane in sorted(set(left_lanes) | set(right_lanes))
    )
    body = {
        "left_execution_id": left.execution_id,
        "right_execution_id": right.execution_id,
        "left_execution_address": left.execution_address,
        "right_execution_address": right.execution_address,
        "left_plan_address": left.plan_address,
        "right_plan_address": right.plan_address,
        "left_metrics_address": left.content_address,
        "right_metrics_address": right.content_address,
        "metrics_changed": left.content_address != right.content_address,
        "event_count_delta": _delta(left.event_count, right.event_count),
        "action_count_delta": _delta(left.action_count, right.action_count),
        "estimate_units_delta": _delta(left.estimate_units, right.estimate_units),
        "completed_estimate_units_delta": _delta(left.completed_estimate_units, right.completed_estimate_units),
        "completion_basis_points_delta": _delta(left.completion_basis_points, right.completion_basis_points),
        "check_coverage_basis_points_delta": _delta(left.check_coverage_basis_points, right.check_coverage_basis_points),
        "required_check_count_delta": _delta(left.required_check_count, right.required_check_count),
        "passed_required_check_count_delta": _delta(left.passed_required_check_count, right.passed_required_check_count),
        "dependency_wait_count_delta": _delta(left.dependency_wait_count, right.dependency_wait_count),
        "active_span_seconds_delta": _optional_delta(left.active_span_seconds, right.active_span_seconds),
        "reopen_count_delta": _delta(left.reopen_count, right.reopen_count),
        "block_count_delta": _delta(left.block_count, right.block_count),
        "skip_count_delta": _delta(left.skip_count, right.skip_count),
        "critical_path_estimate_units_delta": _delta(
            left.critical_path_estimate_units,
            right.critical_path_estimate_units,
        ),
        "critical_path_completed_units_delta": _delta(
            left.critical_path_completed_units,
            right.critical_path_completed_units,
        ),
        "status_count_deltas": _count_deltas(left.status_counts, right.status_counts),
        "event_kind_count_deltas": _count_deltas(left.event_kind_counts, right.event_kind_counts),
        "action_diffs": tuple(item.to_dict() for item in action_diffs),
        "lane_diffs": tuple(item.to_dict() for item in lane_diffs),
        "accepted": left.accepted and right.accepted,
        "warnings": tuple(dict.fromkeys((*left.warnings, *right.warnings))),
    }
    if contains_private_key(body):
        raise ValidationError("metrics diff failed the public boundary")
    return ReviewWorkspaceExecutionMetricsDiff(
        left_execution_id=left.execution_id,
        right_execution_id=right.execution_id,
        left_execution_address=left.execution_address,
        right_execution_address=right.execution_address,
        left_plan_address=left.plan_address,
        right_plan_address=right.plan_address,
        left_metrics_address=left.content_address,
        right_metrics_address=right.content_address,
        metrics_changed=body["metrics_changed"],
        event_count_delta=body["event_count_delta"],
        action_count_delta=body["action_count_delta"],
        estimate_units_delta=body["estimate_units_delta"],
        completed_estimate_units_delta=body["completed_estimate_units_delta"],
        completion_basis_points_delta=body["completion_basis_points_delta"],
        check_coverage_basis_points_delta=body["check_coverage_basis_points_delta"],
        required_check_count_delta=body["required_check_count_delta"],
        passed_required_check_count_delta=body["passed_required_check_count_delta"],
        dependency_wait_count_delta=body["dependency_wait_count_delta"],
        active_span_seconds_delta=body["active_span_seconds_delta"],
        reopen_count_delta=body["reopen_count_delta"],
        block_count_delta=body["block_count_delta"],
        skip_count_delta=body["skip_count_delta"],
        critical_path_estimate_units_delta=body["critical_path_estimate_units_delta"],
        critical_path_completed_units_delta=body["critical_path_completed_units_delta"],
        status_count_deltas=body["status_count_deltas"],
        event_kind_count_deltas=body["event_kind_count_deltas"],
        action_diffs=action_diffs,
        lane_diffs=lane_diffs,
        accepted=body["accepted"],
        warnings=body["warnings"],
        content_address=_address(body, "review-workspace-execution-metrics-diff"),
    )


def review_workspace_execution_metrics_diff_schema() -> dict[str, Any]:
    """Return the public schema for metrics comparisons."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_METRICS_DIFF_SCHEMA_VERSION,
        "diff_version": REVIEW_WORKSPACE_EXECUTION_METRICS_DIFF_VERSION,
        "type": "operational_metrics_comparison",
        "delta_direction": "right minus left",
        "nullable_durations": True,
        "integer_basis_points": True,
        "row_sections": ["action_diffs", "lane_diffs"],
        "aggregate_sections": [
            "status_count_deltas",
            "event_kind_count_deltas",
            "completion_basis_points_delta",
            "check_coverage_basis_points_delta",
            "critical_path_estimate_units_delta",
        ],
        "boundary": {
            "raw_evidence": False,
            "reviewer_identity": False,
            "agent_identity": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "scientific_decision": False,
            "forbidden_keys": sorted(_FORBIDDEN_KEYS),
        },
    }


def review_workspace_execution_metrics_diff_capabilities() -> dict[str, Any]:
    """Return capability metadata without case-specific metrics."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_METRICS_DIFF_VERSION,
        "aggregate_deltas": True,
        "action_level_deltas": True,
        "lane_level_deltas": True,
        "status_count_deltas": True,
        "event_kind_count_deltas": True,
        "nullable_duration_semantics": True,
        "integer_basis_point_deltas": True,
        "content_addressed": True,
        "public_boundary_audit": True,
        "offline_reproducible": True,
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_METRICS_DIFF_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_METRICS_DIFF_VERSION",
    "ReviewWorkspaceExecutionActionMetricsDiff",
    "ReviewWorkspaceExecutionLaneMetricsDiff",
    "ReviewWorkspaceExecutionMetricsDiff",
    "diff_review_workspace_execution_metrics",
    "review_workspace_execution_metrics_diff_capabilities",
    "review_workspace_execution_metrics_diff_schema",
]
