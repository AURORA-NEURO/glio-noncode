"""Deterministic operational metrics for review-plan execution.

Execution reports deliberately model state and replay checks rather than
summary scores.  This module adds a second, derived read model for operators:
how much of the declared work is complete, where time has accumulated, which
lanes are blocked, how many public checks were named, and what the declared
dependency graph's longest estimate path looks like.  Every value is derived
from a typed source plan and a typed replay report; no raw evidence or private
identity is introduced.

Metrics use integer units and basis points instead of floating-point
percentages.  That keeps JSON, CSV, Markdown, and content addresses identical
across runtimes and makes comparisons safe for offline handoffs.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_execution import (
    ReviewPlanActionExecution,
    ReviewPlanExecutionEvent,
    ReviewPlanExecutionEventKind,
    ReviewPlanExecutionStatus,
    ReviewWorkspaceExecutionReport,
)
from .review_workspace_plan import ReviewWorkspacePlan
from .serialization import canonical_json, content_hash, jsonable


REVIEW_WORKSPACE_EXECUTION_METRICS_VERSION = "review-workspace-execution-metrics-v1"
REVIEW_WORKSPACE_EXECUTION_METRICS_SCHEMA_VERSION = (
    "review-workspace-execution-metrics-schema-v1"
)
REVIEW_WORKSPACE_EXECUTION_METRICS_MAX_ROWS = 50_000

_STATUS_VALUES = tuple(item.value for item in ReviewPlanExecutionStatus)
_EVENT_VALUES = tuple(item.value for item in ReviewPlanExecutionEventKind)
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


def _instant(value: str, field: str) -> datetime:
    normalized = _text(value, field)
    candidate = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO-8601 instant") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _canonical_instant(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _seconds(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds()))


def _basis_points(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return min(10_000, max(0, (numerator * 10_000) // denominator))


def _percent_text(basis_points: int) -> str:
    return f"{basis_points // 100}.{basis_points % 100:02d}%"


def _counts(values: Iterable[str], allowed: Iterable[str] = ()) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    for value in allowed:
        counts.setdefault(value, 0)
    return dict(sorted(counts.items()))


def _address(body: Any, prefix: str) -> str:
    return content_hash(body, prefix=prefix)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionActionMetrics:
    """Derived timing and transition measures for one planned action."""

    action_id: str
    lane: str
    action_kind: str
    priority: int
    status: str
    ready: bool
    estimate_units: int
    dependency_count: int
    unresolved_dependency_count: int
    required_check_count: int
    completion_check_count: int
    completion_check_coverage_basis_points: int
    event_count: int
    event_kind_counts: Mapping[str, int]
    first_event_at: str | None
    last_event_at: str | None
    started_at: str | None
    completed_at: str | None
    blocked_at: str | None
    reopened_at: str | None
    active_span_seconds: int | None
    execution_seconds: int | None
    reopen_count: int
    block_count: int
    skip_count: int
    completed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionLaneMetrics:
    """Aggregate operational measures for one declared plan lane."""

    lane: str
    action_count: int
    event_count: int
    estimate_units: int
    completed_estimate_units: int
    completion_basis_points: int
    status_counts: Mapping[str, int]
    event_kind_counts: Mapping[str, int]
    blocked_action_ids: tuple[str, ...]
    dependency_wait_action_ids: tuple[str, ...]
    mean_execution_seconds: int | None
    max_execution_seconds: int | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionMetrics:
    """Complete deterministic metrics projection for one execution report."""

    execution_id: str
    execution_address: str
    plan_id: str
    plan_address: str
    workspace_id: str
    run_id: str
    case_id: str
    version: str
    metrics_version: str
    state: str
    accepted: bool
    event_count: int
    action_count: int
    lane_count: int
    estimate_units: int
    completed_estimate_units: int
    completion_basis_points: int
    status_counts: Mapping[str, int]
    event_kind_counts: Mapping[str, int]
    required_check_count: int
    passed_required_check_count: int
    check_coverage_basis_points: int
    dependency_wait_count: int
    blocked_action_ids: tuple[str, ...]
    dependency_wait_action_ids: tuple[str, ...]
    next_action_ids: tuple[str, ...]
    first_event_at: str | None
    last_event_at: str | None
    active_span_seconds: int | None
    reopen_count: int
    block_count: int
    skip_count: int
    critical_path_action_ids: tuple[str, ...]
    critical_path_estimate_units: int
    critical_path_completed_units: int
    action_metrics: tuple[ReviewWorkspaceExecutionActionMetrics, ...]
    lane_metrics: tuple[ReviewWorkspaceExecutionLaneMetrics, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _action_events(
    report: ReviewWorkspaceExecutionReport,
) -> dict[str, tuple[ReviewPlanExecutionEvent, ...]]:
    grouped: dict[str, list[ReviewPlanExecutionEvent]] = defaultdict(list)
    for event in report.events:
        grouped[event.action_id].append(event)
    return {action_id: tuple(events) for action_id, events in grouped.items()}


def _event_instants(events: Iterable[ReviewPlanExecutionEvent]) -> list[tuple[ReviewPlanExecutionEvent, datetime]]:
    result: list[tuple[ReviewPlanExecutionEvent, datetime]] = []
    for event in events:
        result.append((event, _instant(event.occurred_at, "event.occurred_at")))
    return result


def _latest_event_instant(
    events: Iterable[tuple[ReviewPlanExecutionEvent, datetime]],
    kind: ReviewPlanExecutionEventKind,
) -> datetime | None:
    values = [instant for event, instant in events if event.kind is kind]
    return max(values) if values else None


def _action_metric(
    action: ReviewPlanActionExecution,
    declared_action: Any,
    events: tuple[ReviewPlanExecutionEvent, ...],
) -> ReviewWorkspaceExecutionActionMetrics:
    timed = _event_instants(events)
    instants = [instant for _, instant in timed]
    first = min(instants) if instants else None
    last = max(instants) if instants else None
    started = _latest_event_instant(timed, ReviewPlanExecutionEventKind.START)
    completed = _latest_event_instant(timed, ReviewPlanExecutionEventKind.COMPLETE)
    blocked = _latest_event_instant(timed, ReviewPlanExecutionEventKind.BLOCK)
    reopened = _latest_event_instant(timed, ReviewPlanExecutionEventKind.REOPEN)
    completion_checks = tuple(
        check_id
        for event in reversed(events)
        if event.kind is ReviewPlanExecutionEventKind.COMPLETE
        for check_id in event.check_ids
    )
    completion_check_set = set(completion_checks)
    required_check_set = set(declared_action.required_checks)
    coverage = (
        10_000
        if not required_check_set and action.status is ReviewPlanExecutionStatus.COMPLETED
        else _basis_points(len(required_check_set & completion_check_set), len(required_check_set))
    )
    body = {
        "action_id": action.action_id,
        "lane": action.lane,
        "action_kind": action.action_kind,
        "priority": action.priority,
        "status": action.status.value,
        "ready": action.ready,
        "estimate_units": declared_action.estimate_units,
        "dependency_count": len(declared_action.depends_on),
        "unresolved_dependency_count": len(action.unresolved_dependencies),
        "required_check_count": len(required_check_set),
        "completion_check_count": len(completion_check_set),
        "completion_check_coverage_basis_points": coverage,
        "event_count": len(events),
        "event_kind_counts": _counts((event.kind.value for event in events), _EVENT_VALUES),
        "first_event_at": _canonical_instant(first),
        "last_event_at": _canonical_instant(last),
        "started_at": _canonical_instant(started),
        "completed_at": _canonical_instant(completed),
        "blocked_at": _canonical_instant(blocked),
        "reopened_at": _canonical_instant(reopened),
        "active_span_seconds": _seconds(first, last),
        "execution_seconds": _seconds(started, completed),
        "reopen_count": sum(event.kind is ReviewPlanExecutionEventKind.REOPEN for event in events),
        "block_count": sum(event.kind is ReviewPlanExecutionEventKind.BLOCK for event in events),
        "skip_count": sum(event.kind is ReviewPlanExecutionEventKind.SKIP for event in events),
        "completed": action.status is ReviewPlanExecutionStatus.COMPLETED,
    }
    return ReviewWorkspaceExecutionActionMetrics(
        **body,
        content_address=_address(body, "review-workspace-execution-action-metrics"),
    )


def _lane_metric(
    lane: str,
    rows: tuple[ReviewWorkspaceExecutionActionMetrics, ...],
) -> ReviewWorkspaceExecutionLaneMetrics:
    executions = [row.execution_seconds for row in rows if row.execution_seconds is not None]
    body = {
        "lane": lane,
        "action_count": len(rows),
        "event_count": sum(row.event_count for row in rows),
        "estimate_units": sum(row.estimate_units for row in rows),
        "completed_estimate_units": sum(row.estimate_units for row in rows if row.completed),
        "completion_basis_points": _basis_points(
            sum(row.estimate_units for row in rows if row.completed),
            sum(row.estimate_units for row in rows),
        ),
        "status_counts": _counts((row.status for row in rows), _STATUS_VALUES),
        "event_kind_counts": _counts(
            (
                kind
                for row in rows
                for kind, count in row.event_kind_counts.items()
                for _ in range(count)
            ),
            _EVENT_VALUES,
        ),
        "blocked_action_ids": tuple(sorted(row.action_id for row in rows if row.status == "blocked")),
        "dependency_wait_action_ids": tuple(
            sorted(row.action_id for row in rows if row.unresolved_dependency_count > 0)
        ),
        "mean_execution_seconds": (
            None if not executions else sum(executions) // len(executions)
        ),
        "max_execution_seconds": max(executions) if executions else None,
    }
    return ReviewWorkspaceExecutionLaneMetrics(
        **body,
        content_address=_address(body, "review-workspace-execution-lane-metrics"),
    )


def _critical_path(
    plan: ReviewWorkspacePlan,
    rows: Mapping[str, ReviewWorkspaceExecutionActionMetrics],
) -> tuple[tuple[str, ...], int, int]:
    best: dict[str, tuple[int, tuple[str, ...]]] = {}
    for action in plan.actions:
        candidates = [best[dependency] for dependency in action.depends_on if dependency in best]
        if candidates:
            longest = max(candidates, key=lambda value: (value[0], tuple(value[1])))
            path = longest[1] + (action.action_id,)
            units = longest[0] + action.estimate_units
        else:
            path = (action.action_id,)
            units = action.estimate_units
        best[action.action_id] = (units, path)
    if not best:
        return (), 0, 0
    _, path = max(best.values(), key=lambda value: (value[0], tuple(value[1])))
    completed_units = sum(rows[action_id].estimate_units for action_id in path if rows[action_id].completed)
    return path, best[path[-1]][0], completed_units


def build_review_workspace_execution_metrics(
    plan: ReviewWorkspacePlan,
    report: ReviewWorkspaceExecutionReport,
) -> ReviewWorkspaceExecutionMetrics:
    """Build deterministic metrics from an accepted typed plan and replay report."""

    if not isinstance(plan, ReviewWorkspacePlan):
        raise ValidationError("execution metrics require a typed source plan")
    if not isinstance(report, ReviewWorkspaceExecutionReport):
        raise ValidationError("execution metrics require a typed execution report")
    if not plan.accepted or not report.accepted:
        raise ValidationError("execution metrics require accepted plan and report")
    if plan.plan_id != report.plan_id or plan.content_address != report.plan_address:
        raise ValidationError("execution metrics plan and report addresses differ")
    if len(report.actions) > REVIEW_WORKSPACE_EXECUTION_METRICS_MAX_ROWS:
        raise ValidationError("execution metrics action count exceeds the bound")
    declared = {action.action_id: action for action in plan.actions}
    events_by_action = _action_events(report)
    rows = tuple(
        _action_metric(
            action,
            declared[action.action_id],
            events_by_action.get(action.action_id, ()),
        )
        for action in report.actions
    )
    row_by_id = {row.action_id: row for row in rows}
    lane_values: dict[str, list[ReviewWorkspaceExecutionActionMetrics]] = defaultdict(list)
    for row in rows:
        lane_values[row.lane].append(row)
    lane_rows = tuple(
        _lane_metric(lane, tuple(lane_values[lane])) for lane in sorted(lane_values)
    )
    timed_events = _event_instants(report.events)
    all_instants = [instant for _, instant in timed_events]
    required_checks = [check for check in report.checks if check.required]
    passed_required = [check for check in required_checks if check.passed]
    critical_ids, critical_units, critical_completed = _critical_path(plan, row_by_id)
    body = {
        "metrics_version": REVIEW_WORKSPACE_EXECUTION_METRICS_VERSION,
        "execution_id": report.execution_id,
        "execution_address": report.content_address,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "workspace_id": report.workspace_id,
        "run_id": report.run_id,
        "case_id": report.case_id,
        "version": report.version,
        "state": report.state.value,
        "accepted": report.accepted,
        "event_count": report.event_count,
        "action_count": report.action_count,
        "lane_count": len(lane_rows),
        "estimate_units": sum(row.estimate_units for row in rows),
        "completed_estimate_units": sum(row.estimate_units for row in rows if row.completed),
        "completion_basis_points": _basis_points(
            sum(row.estimate_units for row in rows if row.completed),
            sum(row.estimate_units for row in rows),
        ),
        "status_counts": _counts((row.status for row in rows), _STATUS_VALUES),
        "event_kind_counts": _counts((event.kind.value for event in report.events), _EVENT_VALUES),
        "required_check_count": len(required_checks),
        "passed_required_check_count": len(passed_required),
        "check_coverage_basis_points": _basis_points(len(passed_required), len(required_checks)),
        "dependency_wait_count": report.dependency_wait_count,
        "blocked_action_ids": tuple(sorted(report.blocked_action_ids)),
        "dependency_wait_action_ids": tuple(
            sorted(row.action_id for row in rows if row.unresolved_dependency_count > 0)
        ),
        "next_action_ids": tuple(report.next_action_ids),
        "first_event_at": _canonical_instant(min(all_instants) if all_instants else None),
        "last_event_at": _canonical_instant(max(all_instants) if all_instants else None),
        "active_span_seconds": _seconds(
            min(all_instants) if all_instants else None,
            max(all_instants) if all_instants else None,
        ),
        "reopen_count": sum(event.kind is ReviewPlanExecutionEventKind.REOPEN for event in report.events),
        "block_count": sum(event.kind is ReviewPlanExecutionEventKind.BLOCK for event in report.events),
        "skip_count": sum(event.kind is ReviewPlanExecutionEventKind.SKIP for event in report.events),
        "critical_path_action_ids": critical_ids,
        "critical_path_estimate_units": critical_units,
        "critical_path_completed_units": critical_completed,
        "action_metrics": tuple(row.to_dict() for row in rows),
        "lane_metrics": tuple(row.to_dict() for row in lane_rows),
        "warnings": report.warnings,
    }
    if contains_private_key(body):
        raise ValidationError("execution metrics failed the public boundary")
    metric_fields = {
        key: body[key]
        for key in ReviewWorkspaceExecutionMetrics.__dataclass_fields__
        if key not in {"content_address", "action_metrics", "lane_metrics"}
    }
    return ReviewWorkspaceExecutionMetrics(
        **metric_fields,
        action_metrics=rows,
        lane_metrics=lane_rows,
        content_address=_address(body, "review-workspace-execution-metrics"),
    )


def review_workspace_execution_metrics_json(metrics: ReviewWorkspaceExecutionMetrics) -> str:
    """Render the canonical JSON metrics artifact."""

    return canonical_json(metrics.to_dict()) + "\n"


def review_workspace_execution_metrics_csv(metrics: ReviewWorkspaceExecutionMetrics) -> str:
    """Render one deterministic action-metrics CSV artifact."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "action_id",
            "lane",
            "action_kind",
            "priority",
            "status",
            "ready",
            "estimate_units",
            "dependency_count",
            "unresolved_dependency_count",
            "required_check_count",
            "completion_check_count",
            "completion_check_coverage_basis_points",
            "event_count",
            "first_event_at",
            "last_event_at",
            "started_at",
            "completed_at",
            "blocked_at",
            "reopened_at",
            "active_span_seconds",
            "execution_seconds",
            "reopen_count",
            "block_count",
            "skip_count",
            "completed",
            "content_address",
        )
    )
    for row in metrics.action_metrics:
        writer.writerow(
            (
                row.action_id,
                row.lane,
                row.action_kind,
                row.priority,
                row.status,
                str(row.ready).lower(),
                row.estimate_units,
                row.dependency_count,
                row.unresolved_dependency_count,
                row.required_check_count,
                row.completion_check_count,
                row.completion_check_coverage_basis_points,
                row.event_count,
                row.first_event_at or "",
                row.last_event_at or "",
                row.started_at or "",
                row.completed_at or "",
                row.blocked_at or "",
                row.reopened_at or "",
                "" if row.active_span_seconds is None else row.active_span_seconds,
                "" if row.execution_seconds is None else row.execution_seconds,
                row.reopen_count,
                row.block_count,
                row.skip_count,
                str(row.completed).lower(),
                row.content_address,
            )
        )
    return output.getvalue()


def render_review_workspace_execution_metrics_markdown(
    metrics: ReviewWorkspaceExecutionMetrics,
) -> str:
    """Render a human-readable metrics report without private metadata."""

    lines = [
        "# Review Workspace Execution Metrics",
        "",
        f"- Execution: `{metrics.execution_id}`",
        f"- Execution address: `{metrics.execution_address}`",
        f"- Plan address: `{metrics.plan_address}`",
        f"- State: `{metrics.state}`",
        f"- Completion: `{_percent_text(metrics.completion_basis_points)}`",
        f"- Checks: `{metrics.passed_required_check_count}/{metrics.required_check_count}`",
        f"- Events: `{metrics.event_count}`",
        f"- Critical path estimate units: `{metrics.critical_path_estimate_units}`",
        "",
        "## Lane metrics",
        "",
        "| Lane | Actions | Events | Estimate | Completed | Completion | Blocked | Waits |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in metrics.lane_metrics:
        lines.append(
            f"| {row.lane} | {row.action_count} | {row.event_count} | "
            f"{row.estimate_units} | {row.completed_estimate_units} | "
            f"{_percent_text(row.completion_basis_points)} | {len(row.blocked_action_ids)} | "
            f"{len(row.dependency_wait_action_ids)} |"
        )
    lines.extend(
        [
            "",
            "## Action metrics",
            "",
            "| Action | Lane | Status | Estimate | Events | Execution seconds | Checks |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in metrics.action_metrics:
        seconds = "" if row.execution_seconds is None else str(row.execution_seconds)
        lines.append(
            f"| `{row.action_id}` | {row.lane} | {row.status} | {row.estimate_units} | "
            f"{row.event_count} | {seconds} | "
            f"{_percent_text(row.completion_check_coverage_basis_points)} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This operational projection contains no raw evidence, reviewer identity, agent identity, model metadata, programming-language metadata, or scientific conclusion.",
            "",
        ]
    )
    return "\n".join(lines)


def review_workspace_execution_metrics_export_payloads(
    metrics: ReviewWorkspaceExecutionMetrics,
) -> dict[str, str]:
    """Return canonical payloads used by portable execution releases."""

    return {
        "review-workspace-execution-metrics.json": review_workspace_execution_metrics_json(metrics),
        "review-workspace-execution-metrics.md": render_review_workspace_execution_metrics_markdown(metrics),
        "review-workspace-execution-metrics.csv": review_workspace_execution_metrics_csv(metrics),
    }


def review_workspace_execution_metrics_schema() -> dict[str, Any]:
    """Return the public metrics schema and integer semantics."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_METRICS_SCHEMA_VERSION,
        "metrics_version": REVIEW_WORKSPACE_EXECUTION_METRICS_VERSION,
        "type": "operational_execution_metrics",
        "numeric_semantics": {
            "percentages": "integer basis points where 10000 equals 100 percent",
            "durations": "whole non-negative seconds",
            "estimate_units": "declared plan estimate units",
        },
        "sections": [
            "summary",
            "status_counts",
            "event_kind_counts",
            "action_metrics",
            "lane_metrics",
            "critical_path",
        ],
        "required_fields": [
            "execution_address",
            "plan_address",
            "completion_basis_points",
            "action_metrics",
            "lane_metrics",
            "content_address",
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


def review_workspace_execution_metrics_capabilities() -> dict[str, Any]:
    """Return capability metadata without case-specific metrics."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_METRICS_VERSION,
        "integer_basis_point_percentages": True,
        "action_timing": True,
        "transition_counts": True,
        "lane_aggregation": True,
        "dependency_wait_analysis": True,
        "required_check_coverage": True,
        "critical_path_estimate": True,
        "deterministic_json_csv_markdown": True,
        "content_addressed": True,
        "public_boundary_audit": True,
        "offline_reproducible": True,
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_METRICS_MAX_ROWS",
    "REVIEW_WORKSPACE_EXECUTION_METRICS_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_METRICS_VERSION",
    "ReviewWorkspaceExecutionActionMetrics",
    "ReviewWorkspaceExecutionLaneMetrics",
    "ReviewWorkspaceExecutionMetrics",
    "build_review_workspace_execution_metrics",
    "render_review_workspace_execution_metrics_markdown",
    "review_workspace_execution_metrics_capabilities",
    "review_workspace_execution_metrics_csv",
    "review_workspace_execution_metrics_export_payloads",
    "review_workspace_execution_metrics_json",
    "review_workspace_execution_metrics_schema",
]
