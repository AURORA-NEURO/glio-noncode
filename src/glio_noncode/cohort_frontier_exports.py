"""JSON and CSV exports for Domain 12 review surfaces."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .cohort_frontier_bundle import CohortFrontierReleaseBundle
from .cohort_frontier_release import CohortFrontierReleaseManifest
from .cohort_frontier_views import CohortFrontierReviewView
from .serialization import canonical_json, jsonable


def export_cohort_frontier_json(value: Any, *, indent: int = 2) -> str:
    return json.dumps(jsonable(value), ensure_ascii=False, indent=indent, sort_keys=True) + "\n"


def export_cohort_frontier_canonical(value: Any) -> str:
    return canonical_json(value)


def export_cohort_frontier_manifest(bundle: CohortFrontierReleaseBundle, release: CohortFrontierReleaseManifest) -> dict[str, Any]:
    return {"manifest_type": "cohort_frontier_release", "bundle": bundle.to_dict(), "release": release.to_dict(), "public_boundary": "public_aggregate_non_patient"}


def export_cohort_frontier_review_csv(view: CohortFrontierReviewView) -> str:
    buffer = io.StringIO(newline="")
    fields = ("record_id", "operation", "role", "state", "accepted", "source_count", "issue_codes", "content_address")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in view.rows:
        writer.writerow({"record_id": row.record_id, "operation": row.operation, "role": row.role, "state": row.state, "accepted": str(row.accepted).lower(), "source_count": row.source_count, "issue_codes": ";".join(row.issue_codes), "content_address": row.content_address})
    return buffer.getvalue()


__all__ = ["export_cohort_frontier_canonical", "export_cohort_frontier_json", "export_cohort_frontier_manifest", "export_cohort_frontier_review_csv"]
