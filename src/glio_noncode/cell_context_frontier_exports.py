"""Stable CSV and JSON release exports for Domain 08."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .cell_context_frontier_reports import CellContextFrontierReport
from .cell_context_frontier_views import CellContextFrontierReviewView
from .errors import ValidationError


def export_cell_context_frontier_review_csv(view: CellContextFrontierReviewView) -> str:
    output = io.StringIO()
    fields = (
        "record_id",
        "operation",
        "role",
        "observed_state",
        "decision",
        "issue_codes",
        "candidate_summary",
        "uncertainty",
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


def export_cell_context_frontier_manifest(
    report: CellContextFrontierReport, *, csv_text: str
) -> dict[str, Any]:
    if not csv_text.strip():
        raise ValidationError("cell review CSV must not be empty")
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    return {
        "report_id": report.report_id,
        "fixture_id": report.fixture_id,
        "report_address": report.content_address,
        "section_ids": [item.section_id for item in report.sections],
        "review_csv": {"row_count": len(rows), "content": csv_text},
        "json": json.loads(json.dumps(report.to_dict(), sort_keys=True, default=str)),
    }


__all__ = ["export_cell_context_frontier_manifest", "export_cell_context_frontier_review_csv"]
