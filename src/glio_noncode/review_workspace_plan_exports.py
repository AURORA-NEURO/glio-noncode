"""Deterministic public exports for review-workspace triage plans."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

from .review_workspace_plan import (
    ReviewPlanAction,
    ReviewWorkspacePlan,
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


def review_workspace_plan_actions_csv(plan: ReviewWorkspacePlan) -> str:
    """Render one deterministic action table without hidden payloads."""

    headers = (
        "sequence",
        "action_id",
        "queue_item_id",
        "target_id",
        "target_type",
        "action_kind",
        "lane",
        "priority",
        "state",
        "estimate_units",
        "depends_on",
        "required_checks",
        "edge_ids",
        "evidence_ids",
        "source_ids",
        "content_address",
    )
    rows = (
        (
            item.sequence,
            item.action_id,
            item.queue_item_id,
            item.target_id,
            item.target_type,
            item.action_kind.value,
            item.lane.value,
            item.priority,
            item.state,
            item.estimate_units,
            _join(item.depends_on),
            _join(item.required_checks),
            _join(item.edge_ids),
            _join(item.evidence_ids),
            _join(item.source_ids),
            item.content_address,
        )
        for item in plan.actions
    )
    return _csv_text(headers, rows)


def review_workspace_plan_lanes_csv(plan: ReviewWorkspacePlan) -> str:
    """Render deterministic lane summaries."""

    headers = (
        "lane",
        "action_count",
        "estimate_units",
        "queue_item_ids",
        "action_ids",
        "priority_counts",
        "content_address",
    )
    rows = (
        (
            item.lane.value,
            item.action_count,
            item.estimate_units,
            _join(item.queue_item_ids),
            _join(item.action_ids),
            canonical_json(item.priority_counts),
            item.content_address,
        )
        for item in plan.lanes
    )
    return _csv_text(headers, rows)


def review_workspace_plan_checks_csv(plan: ReviewWorkspacePlan) -> str:
    """Render the plan's structural checks as a deterministic table."""

    headers = (
        "check_id",
        "passed",
        "required",
        "observed",
        "expected",
        "detail",
        "content_address",
    )
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
        for item in plan.checks
    )
    return _csv_text(headers, rows)


def _action_markdown(item: ReviewPlanAction) -> str:
    dependencies = ", ".join(item.depends_on) if item.depends_on else "none"
    checks = ", ".join(item.required_checks) if item.required_checks else "none"
    return "\n".join(
        (
            f"### {item.sequence}. {item.title}",
            "",
            f"- Action: `{item.action_id}`",
            f"- Target: `{item.target_type}:{item.target_id}`",
            f"- Lane: `{item.lane.value}`; priority: `{item.priority}`; estimate: `{item.estimate_units}`",
            f"- State: `{item.state}`",
            f"- Depends on: {dependencies}",
            f"- Required checks: {checks}",
            "",
            item.purpose,
        )
    )


def render_review_workspace_plan_markdown(plan: ReviewWorkspacePlan) -> str:
    """Render a reviewer-readable plan without introducing hidden fields."""

    lines = [
        "# Review workspace plan",
        "",
        f"- Plan: `{plan.plan_id}`",
        f"- Run: `{plan.run_id}`",
        f"- Case: `{plan.case_id}`",
        f"- Workspace address: `{plan.workspace_address}`",
        f"- State: `{plan.state.value}`",
        f"- Accepted: `{str(plan.accepted).lower()}`",
        f"- Queue items: `{plan.queue_item_count}`; actions: `{plan.action_count}`",
        f"- Dependencies: `{plan.dependency_count}`; estimate units: `{plan.estimate_units}`",
        "",
        "This plan describes review work. It does not record a scientific decision or replace human adjudication.",
        "",
        "## Lanes",
        "",
    ]
    if plan.lanes:
        lines.extend(
            f"- `{lane.lane.value}`: {lane.action_count} actions, {lane.estimate_units} estimate units"
            for lane in plan.lanes
        )
    else:
        lines.append("- No lanes were generated.")
    lines.extend(("", "## Structural checks", ""))
    lines.extend(
        f"- `{check.check_id}`: {'passed' if check.passed else 'failed'} — {check.detail}"
        for check in plan.checks
    )
    lines.extend(("", "## Ordered actions", ""))
    if plan.actions:
        lines.extend(_action_markdown(item) + "\n" for item in plan.actions)
    else:
        lines.append("No action rows were exposed.")
    if plan.warnings:
        lines.extend(("", "## Notes", ""))
        lines.extend(f"- {warning}" for warning in plan.warnings)
    lines.extend(("", f"Plan content address: `{plan.content_address}`", ""))
    return "\n".join(lines)


def review_workspace_plan_export_payloads(plan: ReviewWorkspacePlan) -> dict[str, str]:
    """Return the complete deterministic export set for a plan."""

    return {
        "review-workspace-plan.json": canonical_json(jsonable(plan)) + "\n",
        "review-workspace-plan.md": render_review_workspace_plan_markdown(plan),
        "actions.csv": review_workspace_plan_actions_csv(plan),
        "lanes.csv": review_workspace_plan_lanes_csv(plan),
        "checks.csv": review_workspace_plan_checks_csv(plan),
    }


__all__ = [
    "render_review_workspace_plan_markdown",
    "review_workspace_plan_actions_csv",
    "review_workspace_plan_checks_csv",
    "review_workspace_plan_export_payloads",
    "review_workspace_plan_lanes_csv",
]
