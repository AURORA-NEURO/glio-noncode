"""Deterministic exports for review-plan execution reports."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

from .review_workspace_execution import (
    ReviewPlanActionExecution,
    ReviewWorkspaceExecutionReport,
)
from .serialization import canonical_json, jsonable


def _csv_text(headers: tuple[str, ...], rows: Iterable[tuple[Any, ...]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _join(values: Iterable[Any]) -> str:
    return ";".join(str(value) for value in values)


def review_workspace_execution_actions_csv(report: ReviewWorkspaceExecutionReport) -> str:
    """Render action progress, readiness, and dependency state."""

    headers = (
        "sequence",
        "action_id",
        "queue_item_id",
        "target_id",
        "lane",
        "action_kind",
        "priority",
        "status",
        "ready",
        "unresolved_dependencies",
        "event_ids",
        "last_event_id",
        "started_at",
        "completed_at",
        "reason",
        "content_address",
    )
    sequence = {item.action_id: index for index, item in enumerate(report.actions)}
    rows = (
        (
            sequence[item.action_id],
            item.action_id,
            item.queue_item_id,
            item.target_id,
            item.lane,
            item.action_kind,
            item.priority,
            item.status.value,
            str(item.ready).lower(),
            _join(item.unresolved_dependencies),
            _join(item.event_ids),
            item.last_event_id or "",
            item.started_at or "",
            item.completed_at or "",
            item.reason,
            item.content_address,
        )
        for item in report.actions
    )
    return _csv_text(headers, rows)


def review_workspace_execution_events_csv(report: ReviewWorkspaceExecutionReport) -> str:
    """Render the hash-linked event chain as a deterministic table."""

    headers = (
        "sequence",
        "event_id",
        "plan_id",
        "plan_address",
        "action_id",
        "kind",
        "occurred_at",
        "reason",
        "check_ids",
        "reference_addresses",
        "previous_event_address",
        "content_address",
    )
    rows = (
        (
            index,
            item.event_id,
            item.plan_id,
            item.plan_address,
            item.action_id,
            item.kind.value,
            item.occurred_at,
            item.reason,
            _join(item.check_ids),
            _join(item.reference_addresses),
            item.previous_event_address or "",
            item.content_address,
        )
        for index, item in enumerate(report.events)
    )
    return _csv_text(headers, rows)


def review_workspace_execution_checks_csv(report: ReviewWorkspaceExecutionReport) -> str:
    """Render replay invariants."""

    headers = ("check_id", "passed", "required", "observed", "expected", "detail", "content_address")
    rows = (
        (
            item.check_id,
            str(item.passed).lower(),
            str(item.required).lower(),
            canonical_json(jsonable(item.observed)),
            canonical_json(jsonable(item.expected)),
            item.detail,
            item.content_address,
        )
        for item in report.checks
    )
    return _csv_text(headers, rows)


def _action_markdown(item: ReviewPlanActionExecution, sequence: int) -> str:
    dependencies = ", ".join(item.unresolved_dependencies) if item.unresolved_dependencies else "none"
    return "\n".join(
        (
            f"### {sequence}. `{item.action_id}`",
            "",
            f"- Target: `{item.target_id}`; lane: `{item.lane}`; kind: `{item.action_kind}`",
            f"- Status: `{item.status.value}`; ready: `{str(item.ready).lower()}`; priority: `{item.priority}`",
            f"- Unresolved dependencies: {dependencies}",
            f"- Event IDs: {', '.join(item.event_ids) if item.event_ids else 'none'}",
            f"- Reason: {item.reason or 'none'}",
        )
    )


def render_review_workspace_execution_markdown(report: ReviewWorkspaceExecutionReport) -> str:
    """Render a reviewer-readable operational progress report."""

    lines = [
        "# Review workspace plan execution",
        "",
        f"- Execution: `{report.execution_id}`",
        f"- Plan: `{report.plan_id}`",
        f"- Plan address: `{report.plan_address}`",
        f"- Run: `{report.run_id}`",
        f"- State: `{report.state.value}`",
        f"- Accepted: `{str(report.accepted).lower()}`",
        f"- Events: `{report.event_count}`; actions: `{report.action_count}`",
        f"- Open: `{report.open_count}`; in progress: `{report.in_progress_count}`; completed: `{report.completed_count}`",
        f"- Blocked: `{report.blocked_count}`; skipped: `{report.skipped_count}`; dependency-waiting: `{report.dependency_wait_count}`",
        "",
        "Execution records operational progress only. It does not alter scientific evidence or store a scientific decision.",
        "",
        "## Next actions",
        "",
    ]
    lines.extend(f"- `{item}`" for item in report.next_action_ids) or lines.append("- None")
    lines.extend(("", "## Blocked actions", ""))
    lines.extend(f"- `{item}`" for item in report.blocked_action_ids) or lines.append("- None")
    lines.extend(("", "## Replay checks", ""))
    lines.extend(
        f"- `{item.check_id}`: {'passed' if item.passed else 'failed'} — {item.detail}"
        for item in report.checks
    )
    lines.extend(("", "## Actions", ""))
    if report.actions:
        lines.extend(_action_markdown(item, index) + "\n" for index, item in enumerate(report.actions))
    else:
        lines.append("No action rows were exposed.")
    lines.extend(("", "## Event chain", ""))
    if report.events:
        lines.extend(
            f"- `{index}` `{event.kind.value}` `{event.action_id}` at `{event.occurred_at}` address `{event.content_address}`"
            for index, event in enumerate(report.events)
        )
    else:
        lines.append("- No events have been appended.")
    if report.warnings:
        lines.extend(("", "## Notes", ""))
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(("", f"Execution content address: `{report.content_address}`", ""))
    return "\n".join(lines)


def review_workspace_execution_export_payloads(report: ReviewWorkspaceExecutionReport) -> dict[str, str]:
    """Return JSON, Markdown, action, event, and check exports."""

    return {
        "review-workspace-execution.json": canonical_json(jsonable(report)) + "\n",
        "review-workspace-execution.md": render_review_workspace_execution_markdown(report),
        "actions.csv": review_workspace_execution_actions_csv(report),
        "events.csv": review_workspace_execution_events_csv(report),
        "checks.csv": review_workspace_execution_checks_csv(report),
    }


__all__ = [
    "render_review_workspace_execution_markdown",
    "review_workspace_execution_actions_csv",
    "review_workspace_execution_checks_csv",
    "review_workspace_execution_events_csv",
    "review_workspace_execution_export_payloads",
]
