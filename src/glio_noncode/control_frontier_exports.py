"""JSON, CSV, and markdown projections for control frontier results."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation
from .control_frontier_views import ControlFrontierView


def export_control_frontier_json(evaluation: ControlFrontierEvaluation) -> str:
    return json.dumps(evaluation.to_dict(), sort_keys=True, separators=(",", ":"))


def export_control_frontier_review_csv(view: ControlFrontierView) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=("record_id", "operation", "role", "state", "accepted", "issue_codes"))
    writer.writeheader()
    for item in view.entries:
        writer.writerow({"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "state": item.state.value, "accepted": item.accepted, "issue_codes": "|".join(item.issue_codes)})
    return buffer.getvalue()


def export_control_frontier_metrics_csv(evaluation: ControlFrontierEvaluation) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=("record_id", "operation", "state", "accepted", "issue_count"))
    writer.writeheader()
    for item in evaluation.executions:
        writer.writerow({"record_id": item.record_id, "operation": item.operation.value, "state": item.state.value, "accepted": item.accepted, "issue_count": len(item.issue_codes)})
    return buffer.getvalue()


def render_control_frontier_review_markdown(view: ControlFrontierView) -> str:
    lines = ["# Control frontier review", "", f"Fixture: `{view.fixture_id}`", "", "| Row | Operation | Role | State | Issues |", "|---|---|---|---|---|"]
    lines.extend(f"| {item.record_id} | {item.operation.value} | {item.role.value} | {item.state.value} | {', '.join(item.issue_codes) or 'none'} |" for item in view.entries)
    return "\n".join(lines) + "\n"


__all__ = ["export_control_frontier_json", "export_control_frontier_metrics_csv", "export_control_frontier_review_csv", "render_control_frontier_review_markdown"]
