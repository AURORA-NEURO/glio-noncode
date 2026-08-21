"""Stable CSV, Markdown, and JSON exports for C13-C16."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .frontier_atlas_fixture_eval import FrontierAtlasEvaluationReport
from .frontier_atlas_metrics import FrontierAtlasMetrics
from .frontier_atlas_release import FrontierAtlasReleaseManifest
from .frontier_atlas_views import FrontierAtlasView
from .serialization import content_hash


def _csv_text(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return stream.getvalue()


def export_frontier_atlas_receipts_csv(evaluation: FrontierAtlasEvaluationReport) -> str:
    fields = (
        "record_id",
        "operation",
        "role",
        "context_key",
        "adapter_state",
        "primary_count",
        "secondary_count",
        "observed_issue_codes",
        "expected_state",
        "content_address",
    )
    rows = [
        {
            "record_id": item.record_id,
            "operation": item.operation.value,
            "role": item.role.value,
            "context_key": item.context_key,
            "adapter_state": item.adapter_state,
            "primary_count": item.primary_count,
            "secondary_count": item.secondary_count,
            "observed_issue_codes": "|".join(item.observed_issue_codes),
            "expected_state": item.expected_state,
            "content_address": item.content_address,
        }
        for item in evaluation.receipts
    ]
    return _csv_text(rows, fields)


def export_frontier_atlas_review_csv(view: FrontierAtlasView) -> str:
    fields = (
        "record_id",
        "operation",
        "role",
        "state",
        "priority",
        "action",
        "issue_codes",
        "context_key",
        "content_address",
    )
    rows = [
        {
            "record_id": item.record_id,
            "operation": item.operation.value,
            "role": item.role.value,
            "state": item.state,
            "priority": item.priority,
            "action": item.action,
            "issue_codes": "|".join(item.issue_codes),
            "context_key": item.context_key,
            "content_address": item.content_address,
        }
        for item in view.review_queue
    ]
    return _csv_text(rows, fields)


def export_frontier_atlas_metrics_csv(metrics: FrontierAtlasMetrics) -> str:
    fields = (
        "operation",
        "record_count",
        "positive_count",
        "control_count",
        "accepted_count",
        "published_count",
        "review_count",
        "issue_count",
        "content_address",
    )
    rows = [
        {
            "operation": item.operation.value,
            "record_count": item.record_count,
            "positive_count": item.positive_count,
            "control_count": item.control_count,
            "accepted_count": item.accepted_count,
            "published_count": item.published_count,
            "review_count": item.review_count,
            "issue_count": item.issue_count,
            "content_address": item.content_address,
        }
        for item in metrics.operation_metrics
    ]
    return _csv_text(rows, fields)


def render_frontier_atlas_review_markdown(view: FrontierAtlasView) -> str:
    lines = [
        "# Frontier atlas review",
        "",
        f"- Fixture: `{view.fixture_id}`",
        f"- Context: `{view.context_key}`",
        f"- Review rows: `{view.review_count}`",
        "",
        "| Record | Operation | State | Priority | Action | Issues |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in view.review_queue:
        lines.append(
            f"| `{item.record_id}` | `{item.operation.value}` | `{item.state}` | {item.priority} | `{item.action}` | `{', '.join(item.issue_codes) or 'none'}` |"
        )
    lines.extend(("", f"Content address: `{view.content_address}`", ""))
    return "\n".join(lines)


def render_frontier_atlas_release_markdown(manifest: FrontierAtlasReleaseManifest) -> str:
    lines = [
        "# Frontier atlas release",
        "",
        f"- Release: `{manifest.release_id}`",
        f"- Version: `{manifest.release_version}`",
        f"- Fixture: `{manifest.fixture_id}`",
        f"- Context: `{manifest.context_key}`",
        f"- Status: `{manifest.status}`",
        "",
        "## Operations",
        "",
    ]
    lines.extend(f"- `{operation}`" for operation in manifest.operation_ids)
    lines.extend(("", "## Sources", ""))
    lines.extend(f"- `{source}`" for source in manifest.source_ids)
    lines.extend(
        (
            "",
            manifest.acceptance_statement,
            "",
            f"Bundle address: `{manifest.bundle_address}`",
            f"Quality address: `{manifest.quality_address}`",
            f"Runtime address: `{manifest.runtime_address}`",
            f"Manifest address: `{manifest.content_address}`",
            "",
        )
    )
    return "\n".join(lines)


def export_frontier_atlas_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def frontier_atlas_export_receipt(export_name: str, payload: str) -> dict[str, Any]:
    body = {
        "export_name": export_name,
        "byte_count": len(payload.encode("utf-8")),
        "line_count": payload.count("\n"),
        "payload": payload,
    }
    return {key: value for key, value in body.items() if key != "payload"} | {
        "content_address": content_hash(body)
    }


__all__ = [
    "export_frontier_atlas_json",
    "export_frontier_atlas_metrics_csv",
    "export_frontier_atlas_receipts_csv",
    "export_frontier_atlas_review_csv",
    "frontier_atlas_export_receipt",
    "render_frontier_atlas_release_markdown",
    "render_frontier_atlas_review_markdown",
]
