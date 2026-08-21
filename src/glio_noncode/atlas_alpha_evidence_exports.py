"""Stable text exports for C09-C12 review and release surfaces."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .atlas_alpha_evidence_fixture_eval import AtlasAlphaEvidenceEvaluationReport
from .atlas_alpha_evidence_metrics import AtlasAlphaEvidenceMetrics
from .atlas_alpha_evidence_release import AtlasAlphaEvidenceReleaseManifest
from .atlas_alpha_evidence_views import AtlasAlphaEvidenceView
from .serialization import content_hash


def _csv_text(rows: list[dict[str, Any]], fieldnames: tuple[str, ...]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return stream.getvalue()


def export_atlas_alpha_evidence_receipts_csv(evaluation: AtlasAlphaEvidenceEvaluationReport) -> str:
    """Export sanitized receipts as deterministic CSV."""

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


def export_atlas_alpha_evidence_review_csv(view: AtlasAlphaEvidenceView) -> str:
    """Export only non-supported review rows."""

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


def export_atlas_alpha_evidence_metrics_csv(metrics: AtlasAlphaEvidenceMetrics) -> str:
    """Export operation metrics with integer counts and rates."""

    fields = (
        "operation",
        "record_count",
        "positive_count",
        "control_count",
        "supported_count",
        "review_count",
        "issue_count",
        "acceptance_rate",
        "content_address",
    )
    rows = [
        {
            "operation": item.operation.value,
            "record_count": item.record_count,
            "positive_count": item.positive_count,
            "control_count": item.control_count,
            "supported_count": item.supported_count,
            "review_count": item.review_count,
            "issue_count": item.issue_count,
            "acceptance_rate": f"{item.acceptance_rate:.6f}",
            "content_address": item.content_address,
        }
        for item in metrics.operation_metrics
    ]
    return _csv_text(rows, fields)


def render_atlas_alpha_evidence_review_markdown(view: AtlasAlphaEvidenceView) -> str:
    """Render a compact review table with an address footer."""

    lines = [
        "# Atlas-alpha evidence review",
        "",
        f"- Fixture: `{view.fixture_id}`",
        f"- Context: `{view.context_key}`",
        f"- Review rows: `{view.review_count}`",
        "",
        "| Record | Operation | State | Priority | Action | Issues |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in view.review_queue:
        issues = ", ".join(item.issue_codes) or "none"
        lines.append(
            f"| `{item.record_id}` | `{item.operation.value}` | `{item.state}` | {item.priority} | `{item.action}` | `{issues}` |"
        )
    lines.extend(("", f"Content address: `{view.content_address}`", ""))
    return "\n".join(lines)


def render_atlas_alpha_evidence_release_markdown(
    manifest: AtlasAlphaEvidenceReleaseManifest,
) -> str:
    """Render a release handoff with source and operation closure."""

    lines = [
        "# Atlas-alpha evidence release",
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


def export_atlas_alpha_evidence_json(payload: Any) -> str:
    """Serialize an accepted artifact with stable key ordering."""

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atlas_alpha_evidence_export_receipt(export_name: str, payload: str) -> dict[str, Any]:
    """Address an emitted text artifact for downstream auditing."""

    return {
        "export_name": export_name,
        "byte_count": len(payload.encode("utf-8")),
        "line_count": payload.count("\n"),
        "content_address": content_hash({"export_name": export_name, "payload": payload}),
    }


__all__ = [
    "atlas_alpha_evidence_export_receipt",
    "export_atlas_alpha_evidence_json",
    "export_atlas_alpha_evidence_metrics_csv",
    "export_atlas_alpha_evidence_receipts_csv",
    "export_atlas_alpha_evidence_review_csv",
    "render_atlas_alpha_evidence_release_markdown",
    "render_atlas_alpha_evidence_review_markdown",
]
