"""JSON, CSV, and markdown exports for the C05-C12 review package."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from .lifecycle_beta_frontier_metrics import LifecycleBetaFrontierMetrics
from .lifecycle_beta_frontier_release import LifecycleBetaFrontierReleaseManifest
from .lifecycle_beta_frontier_views import LifecycleBetaFrontierView
from .serialization import content_hash


def lifecycle_beta_frontier_export_payload(value: Any) -> dict[str, Any]:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    if not isinstance(payload, dict):
        raise TypeError("lifecycle frontier export requires a mapping payload")
    return payload


def export_lifecycle_beta_frontier_json(value: Any, path: str | Path) -> str:
    payload = lifecycle_beta_frontier_export_payload(value)
    output = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(output, encoding="utf-8")
    return content_hash(payload)


def export_lifecycle_beta_frontier_review_csv(view: LifecycleBetaFrontierView, path: str | Path) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=("record_id", "operation", "role", "state", "issue_codes", "accepted", "detail"))
    writer.writeheader()
    for item in view.entries:
        writer.writerow({"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "state": item.state.value, "issue_codes": "|".join(item.issue_codes), "accepted": item.accepted, "detail": item.detail})
    output = buffer.getvalue()
    Path(path).write_text(output, encoding="utf-8")
    return content_hash(output)


def export_lifecycle_beta_frontier_metrics_csv(metrics: LifecycleBetaFrontierMetrics, path: str | Path) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=("operation", "record_count", "positive_count", "control_count", "accepted_count", "state_counts", "issue_counts"))
    writer.writeheader()
    for item in metrics.operation_metrics:
        writer.writerow({"operation": item.operation.value, "record_count": item.record_count, "positive_count": item.positive_count, "control_count": item.control_count, "accepted_count": item.accepted_count, "state_counts": json.dumps(item.state_counts, sort_keys=True), "issue_counts": json.dumps(item.issue_counts, sort_keys=True)})
    output = buffer.getvalue()
    Path(path).write_text(output, encoding="utf-8")
    return content_hash(output)


def render_lifecycle_beta_frontier_review_markdown(view: LifecycleBetaFrontierView, release: LifecycleBetaFrontierReleaseManifest | None = None) -> str:
    lines = [
        "# Lifecycle-beta frontier research review",
        "",
        "This is a public aggregate, research-use-only review surface. It is not a patient-level or clinical result.",
        "",
        "| Record | Operation | Role | State | Issues | Accepted |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in view.entries:
        lines.append(f"| {item.record_id} | {item.operation.value} | {item.role.value} | {item.state.value} | {', '.join(item.issue_codes) or 'none'} | {'yes' if item.accepted else 'no'} |")
    lines.extend(("", "## State counts", "", json.dumps(view.state_counts, indent=2, sort_keys=True), "", "## Content address", "", "sha256: " + view.content_address))
    if release is not None:
        lines.extend(("", "## Release boundary", "", f"- Accepted: {release.accepted}", f"- Research use only: {release.research_use_only}", f"- Required review: {', '.join(release.required_review) or 'none'}"))
    return "\n".join(lines) + "\n"


__all__ = ["export_lifecycle_beta_frontier_json", "export_lifecycle_beta_frontier_metrics_csv", "export_lifecycle_beta_frontier_review_csv", "lifecycle_beta_frontier_export_payload", "render_lifecycle_beta_frontier_review_markdown"]
