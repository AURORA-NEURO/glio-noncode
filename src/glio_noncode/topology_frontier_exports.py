"""Sanitized JSON, CSV, and Markdown exports for Domain 09."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .serialization import content_hash, jsonable
from .topology_frontier_fixture_eval import TopologyFrontierEvaluationReport
from .topology_frontier_metrics import TopologyFrontierMetrics
from .topology_frontier_release import TopologyFrontierReleaseManifest
from .topology_frontier_views import TopologyFrontierView, topology_frontier_review_summary


def _csv_text(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return stream.getvalue()


def export_topology_frontier_receipts_csv(evaluation: TopologyFrontierEvaluationReport) -> str:
    fields = ("record_id", "operation", "role", "context_key", "adapter_state", "primary_count", "secondary_count", "observed_issue_codes", "expected_state", "content_address")
    rows = [{"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "context_key": item.context_key, "adapter_state": item.adapter_state, "primary_count": item.primary_count, "secondary_count": item.secondary_count, "observed_issue_codes": "|".join(item.observed_issue_codes), "expected_state": item.expected_state, "content_address": item.content_address} for item in evaluation.receipts]
    return _csv_text(rows, fields)


def export_topology_frontier_review_csv(view: TopologyFrontierView) -> str:
    fields = ("record_id", "operation", "role", "state", "priority", "action", "issue_codes", "context_key", "content_address")
    rows = [{"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "state": item.state, "priority": item.priority, "action": item.action, "issue_codes": "|".join(item.issue_codes), "context_key": item.context_key, "content_address": item.content_address} for item in view.review_queue]
    return _csv_text(rows, fields)


def export_topology_frontier_metrics_csv(metrics: TopologyFrontierMetrics) -> str:
    fields = ("operation", "record_count", "positive_count", "control_count", "supported_count", "review_count", "out_of_domain_count", "invalid_count", "issue_count", "content_address")
    rows = [{"operation": item.operation.value, "record_count": item.record_count, "positive_count": item.positive_count, "control_count": item.control_count, "supported_count": item.supported_count, "review_count": item.review_count, "out_of_domain_count": item.out_of_domain_count, "invalid_count": item.invalid_count, "issue_count": item.issue_count, "content_address": item.content_address} for item in metrics.operation_metrics]
    return _csv_text(rows, fields)


def render_topology_frontier_review_markdown(view: TopologyFrontierView) -> str:
    summary = topology_frontier_review_summary(view)
    lines = ["# Topology frontier review", "", f"- Fixture: `{view.fixture_id}`", f"- Context: `{view.context_key}`", f"- Boundary: `{view.evidence_boundary}`", f"- Review rows: **{view.review_count}**", "", "| Record | Operation | State | Priority | Issue codes | Action |", "| --- | --- | --- | ---: | --- | --- |"]
    for item in view.review_queue:
        lines.append(f"| `{item.record_id}` | `{item.operation.value}` | `{item.state}` | {item.priority} | {', '.join(item.issue_codes) or 'none'} | {item.action} |")
    lines.extend(("", "## Summary", "", f"State counts: `{summary['state_counts']}`.", f"Operation counts: `{summary['operation_counts']}`.", "", "Review rows retain topology uncertainty and scope controls; they are not success records."))
    return "\n".join(lines) + "\n"


def render_topology_frontier_release_markdown(release: TopologyFrontierReleaseManifest) -> str:
    return "\n".join(("# Topology frontier release", "", f"- Release: `{release.release_id}`", f"- Fixture: `{release.fixture_id}`", f"- Version: `{release.fixture_version}`", f"- Run: `{release.run_id}`", f"- Context: `{release.context_key}`", f"- Boundary: `{release.evidence_boundary}`", f"- State: **{release.release_state}**", f"- Sources: `{', '.join(release.source_ids)}`", f"- Bundle address: `{release.bundle_address}`", f"- Records address: `{release.record_address}`", "", "The manifest records descriptive three-dimensional topology evidence and its review boundary.")) + "\n"


def export_topology_frontier_json(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, indent=2) + "\n"


def topology_frontier_export_receipt(export_name: str, payload: str) -> dict[str, Any]:
    body = {"export_name": export_name, "byte_count": len(payload.encode("utf-8")), "payload": payload}
    return {"export_name": export_name, "byte_count": body["byte_count"], "content_address": content_hash(body)}


__all__ = [
    "export_topology_frontier_json",
    "export_topology_frontier_metrics_csv",
    "export_topology_frontier_receipts_csv",
    "export_topology_frontier_review_csv",
    "render_topology_frontier_release_markdown",
    "render_topology_frontier_review_markdown",
    "topology_frontier_export_receipt",
]
