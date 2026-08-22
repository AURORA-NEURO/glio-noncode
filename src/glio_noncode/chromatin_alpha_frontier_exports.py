"""Deterministic CSV, JSON, and Markdown projections."""

from __future__ import annotations

import csv
import io
from typing import Any

from .chromatin_alpha_frontier_reports import ChromatinAlphaFrontierReport
from .chromatin_alpha_frontier_views import ChromatinAlphaFrontierReviewView
from .serialization import canonical_json, content_hash


def export_chromatin_alpha_frontier_review_csv(
    view: ChromatinAlphaFrontierReviewView,
) -> str:
    columns = (
        "row_id",
        "record_id",
        "operation",
        "role",
        "state",
        "decision",
        "expected_state",
        "state_match",
        "issue_codes",
        "source_ids",
        "context_key",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in view.rows:
        writer.writerow(
            {
                "row_id": row.row_id,
                "record_id": row.record_id,
                "operation": row.operation,
                "role": row.role,
                "state": row.state,
                "decision": row.decision,
                "expected_state": row.expected_state,
                "state_match": str(row.state_match).lower(),
                "issue_codes": "|".join(row.issue_codes),
                "source_ids": "|".join(row.source_ids),
                "context_key": row.context_key,
                "content_address": row.content_address,
            }
        )
    return output.getvalue()


def export_chromatin_alpha_frontier_json(report: ChromatinAlphaFrontierReport) -> str:
    return canonical_json(report.to_dict())


def render_chromatin_alpha_frontier_review_markdown(view: ChromatinAlphaFrontierReviewView) -> str:
    lines = [
        "# Chromatin-alpha frontier review",
        "",
        f"Fixture: `{view.fixture_id}`",
        f"Context: `{view.rows[0].context_key}`",
        "",
        "| Record | Operation | Role | State | Decision | Issues |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        (
            f"| {row.record_id} | {row.operation} | {row.role} | {row.state} | "
            f"{row.decision} | {', '.join(row.issue_codes) or 'none'} |"
        )
        for row in view.rows
    )
    return "\n".join(lines) + "\n"


def export_chromatin_alpha_frontier_manifest(
    report: ChromatinAlphaFrontierReport,
    *,
    csv_text: str = "",
) -> dict[str, Any]:
    body = {
        "report_id": report.report_id,
        "fixture_id": report.fixture_id,
        "report_address": report.content_address,
        "csv_address": content_hash(csv_text),
        "section_ids": [section.section_id for section in report.sections],
        "accepted": report.accepted,
    }
    return body | {"manifest_address": content_hash(body)}


__all__ = [
    "export_chromatin_alpha_frontier_json",
    "export_chromatin_alpha_frontier_manifest",
    "export_chromatin_alpha_frontier_review_csv",
    "render_chromatin_alpha_frontier_review_markdown",
]
