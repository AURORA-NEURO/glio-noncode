"""Stable JSON and CSV exports for release and review consumers."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .chromatin_context_frontier_reports import ChromatinContextFrontierReport
from .chromatin_context_frontier_views import ChromatinContextFrontierReviewView
from .errors import ValidationError


def export_chromatin_context_frontier_review_csv(
    view: ChromatinContextFrontierReviewView,
) -> str:
    output = io.StringIO()
    fields = (
        "record_id",
        "operation",
        "role",
        "observed_state",
        "decision",
        "issue_codes",
        "signal_summary",
        "review_required",
        "release_eligible",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in view.rows:
        data = row.to_dict()
        data["issue_codes"] = ";".join(row.issue_codes)
        writer.writerow({field: data[field] for field in fields})
    return output.getvalue()


def export_chromatin_context_frontier_manifest(
    report: ChromatinContextFrontierReport,
    *,
    csv_text: str,
) -> dict[str, Any]:
    if not csv_text.strip():
        raise ValidationError("review CSV must not be empty")
    try:
        rows = list(csv.DictReader(io.StringIO(csv_text)))
    except csv.Error as error:
        raise ValidationError("review CSV is invalid") from error
    return {
        "report_id": report.report_id,
        "fixture_id": report.fixture_id,
        "report_address": report.content_address,
        "section_ids": [item.section_id for item in report.sections],
        "review_csv": {
            "row_count": len(rows),
            "content": csv_text,
        },
        "json": json.loads(json.dumps(report.to_dict(), sort_keys=True, default=str)),
    }


__all__ = [
    "export_chromatin_context_frontier_manifest",
    "export_chromatin_context_frontier_review_csv",
]
