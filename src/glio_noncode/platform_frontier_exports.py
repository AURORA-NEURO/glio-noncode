"""Deterministic JSON, CSV, and Markdown exports for platform views."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation
from .platform_frontier_metrics import PlatformFrontierMetrics
from .platform_frontier_views import PlatformFrontierView
from .serialization import jsonable


def export_platform_frontier_json(value: Any) -> str:
    return json.dumps(jsonable(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def export_platform_frontier_review_csv(view: PlatformFrontierView) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("record_id", "role", "operation", "state", "accepted", "review_required", "issue_codes"))
    for row in view.entries:
        writer.writerow((row.record_id, row.role.value, row.operation, row.state, str(row.accepted).lower(), str(row.review_required).lower(), ";".join(row.issue_codes)))
    return output.getvalue()


def export_platform_frontier_metrics_csv(metrics: PlatformFrontierMetrics) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("operation", "record_count", "positive_count", "control_count", "accepted_count", "states", "issues"))
    for row in metrics.operation_metrics:
        writer.writerow((row.operation.value, row.record_count, row.positive_count, row.control_count, row.accepted_count, json.dumps(row.state_counts, sort_keys=True), json.dumps(row.issue_counts, sort_keys=True)))
    return output.getvalue()


def render_platform_frontier_review_markdown(view: PlatformFrontierView) -> str:
    lines = ["# Platform review", "", "| Record | Role | Operation | State | Accepted | Issues |", "| --- | --- | --- | --- | --- | --- |"]
    for row in view.entries:
        lines.append(f"| {row.record_id} | {row.role.value} | {row.operation} | {row.state} | {row.accepted} | {', '.join(row.issue_codes) or 'none'} |")
    return "\n".join(lines) + "\n"


__all__ = ["export_platform_frontier_json", "export_platform_frontier_metrics_csv", "export_platform_frontier_review_csv", "render_platform_frontier_review_markdown"]
