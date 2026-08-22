"""Canonical export functions for reference release reports."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .reference_release_frontier_bundle import ReferenceReleaseEvidenceBundle
from .reference_release_frontier_metrics import (
    ReferenceReleaseMetricsReport,
    render_reference_release_metrics,
)
from .reference_release_frontier_release import ReferenceReleaseManifest
from .serialization import jsonable


def export_reference_release_json(value: Any) -> str:
    """Serialize any public report with stable indentation and a terminal newline."""

    return json.dumps(jsonable(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def export_reference_release_manifest(manifest: ReferenceReleaseManifest) -> str:
    """Export a release manifest as canonical JSON."""

    return export_reference_release_json(manifest)


def export_reference_release_metrics(report: ReferenceReleaseMetricsReport) -> str:
    """Export the compact metrics dashboard."""

    return export_reference_release_json(render_reference_release_metrics(report))


def export_reference_release_bundle_csv(bundle: ReferenceReleaseEvidenceBundle) -> str:
    """Export bundle entries with fixed columns and no raw payload fields."""

    buffer = io.StringIO()
    fields = (
        "record_id",
        "operation",
        "role",
        "state",
        "accepted",
        "issue_codes",
        "receipt_address",
        "content_address",
    )
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for entry in bundle.entries:
        row = entry.to_dict()
        row["issue_codes"] = "|".join(row["issue_codes"])
        writer.writerow({field: row[field] for field in fields})
    return buffer.getvalue()


def export_reference_release_addresses(value: Any) -> dict[str, str]:
    """Extract direct address fields for API consumers."""

    data = jsonable(value)
    if not isinstance(data, dict):
        return {}
    return {
        key: str(item)
        for key, item in data.items()
        if key.endswith("address") or key == "content_address"
    }


__all__ = [
    "export_reference_release_addresses",
    "export_reference_release_bundle_csv",
    "export_reference_release_json",
    "export_reference_release_manifest",
    "export_reference_release_metrics",
]
