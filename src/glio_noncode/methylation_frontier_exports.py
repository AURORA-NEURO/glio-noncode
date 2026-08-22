"""Deterministic exports for methylation review and release records."""

from __future__ import annotations

import csv
import io
from typing import Any

from .methylation_frontier_reports import MethylationFrontierReport
from .methylation_frontier_views import MethylationFrontierReviewView
from .serialization import canonical_json, content_hash


def export_methylation_frontier_review_rows(view: MethylationFrontierReviewView) -> str:
    """Return a stable CSV with only review-safe fields."""

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


def export_methylation_frontier_json(report: MethylationFrontierReport) -> str:
    return canonical_json(report.to_dict())


def export_methylation_frontier_manifest(
    report: MethylationFrontierReport,
    *,
    csv_text: str | None = None,
) -> dict[str, Any]:
    csv_text = csv_text or ""
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
    "export_methylation_frontier_json",
    "export_methylation_frontier_manifest",
    "export_methylation_frontier_review_rows",
]
