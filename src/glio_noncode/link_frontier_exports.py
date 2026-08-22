"""Sanitized JSON, CSV, and Markdown exports for Domain 10."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .link_frontier_fixture_eval import LinkFrontierEvaluation
from .link_frontier_metrics import LinkFrontierMetrics
from .link_frontier_release import LinkFrontierReleaseManifest
from .link_frontier_views import LinkFrontierView, link_frontier_review_summary
from .serialization import content_hash, jsonable


def _csv_text(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return stream.getvalue()


def export_link_frontier_json(value: Any) -> str:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    return json.dumps(jsonable(payload), sort_keys=True, indent=2) + "\n"


def export_link_frontier_receipts_csv(evaluation: LinkFrontierEvaluation) -> str:
    fields = ("record_id", "operation", "role", "context_key", "state", "issue_codes", "error", "content_address")
    rows = [{"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "context_key": item.context_key, "state": item.state, "issue_codes": "|".join(item.issue_codes), "error": item.error or "", "content_address": item.content_address} for item in evaluation.executions]
    return _csv_text(rows, fields)


def export_link_frontier_review_csv(view: LinkFrontierView) -> str:
    fields = ("record_id", "operation", "role", "state", "priority", "issue_codes", "action", "context_key", "content_address")
    rows = [{"record_id": item.record_id, "operation": item.operation.value, "role": item.role, "state": item.state, "priority": item.priority, "issue_codes": "|".join(item.issue_codes), "action": item.action, "context_key": item.context_key, "content_address": item.content_address} for item in view.review_queue]
    return _csv_text(rows, fields)


def export_link_frontier_metrics_csv(metrics: LinkFrontierMetrics) -> str:
    fields = ("fixture_id", "record_count", "positive_count", "control_count", "execution_count", "passed_check_count", "failed_check_count", "positive_acceptance_rate", "control_rejection_rate", "content_address")
    return _csv_text([metrics.to_dict()], fields)


def render_link_frontier_review_markdown(view: LinkFrontierView) -> str:
    summary = link_frontier_review_summary(view)
    lines = ["# Link frontier review", "", f"- Fixture: `{view.fixture_id}`", f"- Context: `{view.context_key}`", f"- Boundary: `{view.evidence_boundary}`", f"- Review rows: **{view.review_count}**", "", "| Record | Operation | State | Priority | Issue codes | Action |", "| --- | --- | --- | ---: | --- | --- |"]
    for item in view.review_queue:
        lines.append(f"| `{item.record_id}` | `{item.operation.value}` | `{item.state}` | {item.priority} | {', '.join(item.issue_codes) or 'none'} | {item.action} |")
    lines.extend(("", "## Summary", "", f"State counts: `{summary['state_counts']}`.", f"Operation counts: `{summary['operation_counts']}`.", "", "Review rows retain uncertainty, alternatives, and scope controls; they are not causal or clinical conclusions."))
    return "\n".join(lines) + "\n"


def render_link_frontier_release_markdown(release: LinkFrontierReleaseManifest) -> str:
    return "\n".join(("# Link frontier release", "", f"- Release: `{release.release_id}`", f"- Fixture: `{release.fixture_id}`", f"- Version: `{release.release_version}`", f"- Context: `{release.context_key}`", f"- Boundary: `{release.evidence_boundary}`", f"- State: **{release.state}**", f"- Records: `{release.record_count}`", f"- Sources: `{release.source_count}`", f"- Manifest address: `{release.content_address}`", "", "The manifest records descriptive candidate-link evidence and its review boundary.")) + "\n"


def link_frontier_export_receipt(export_name: str, payload: str) -> dict[str, Any]:
    body = {"export_name": export_name, "byte_count": len(payload.encode("utf-8")), "payload": payload}
    return {"export_name": export_name, "byte_count": body["byte_count"], "content_address": content_hash(body)}


__all__ = [
    "export_link_frontier_json",
    "export_link_frontier_metrics_csv",
    "export_link_frontier_receipts_csv",
    "export_link_frontier_review_csv",
    "link_frontier_export_receipt",
    "render_link_frontier_release_markdown",
    "render_link_frontier_review_markdown",
]
