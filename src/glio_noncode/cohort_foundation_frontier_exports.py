"""Stable JSON, CSV, and Markdown exports for the foundation frontier."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .serialization import jsonable
from .cohort_foundation_frontier_bundle import CohortFoundationReleaseBundle
from .cohort_foundation_frontier_release import CohortFoundationReleaseManifest
from .cohort_foundation_frontier_review import CohortFoundationReviewQueue


def export_cohort_foundation_frontier_json(value: Any, *, indent: int = 2) -> str:
    return json.dumps(jsonable(value), sort_keys=True, indent=indent, default=str)


def export_cohort_foundation_frontier_canonical(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), default=str)


def export_cohort_foundation_frontier_manifest(bundle: CohortFoundationReleaseBundle, release: CohortFoundationReleaseManifest) -> dict[str, Any]:
    return {"manifest_type": "cohort_foundation_frontier_release", "public_boundary": bundle.fixture.boundary, "bundle": jsonable(bundle), "release": jsonable(release)}


def export_cohort_foundation_frontier_review_csv(queue: CohortFoundationReviewQueue) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=("review_id", "record_id", "operation", "severity", "disposition", "issue_codes", "required_action"), lineterminator="\n")
    writer.writeheader()
    for item in queue.items:
        writer.writerow({"review_id": item.review_id, "record_id": item.record_id, "operation": item.operation, "severity": item.severity.value, "disposition": item.disposition.value, "issue_codes": "|".join(item.issue_codes), "required_action": item.required_action})
    return output.getvalue()


def export_cohort_foundation_frontier_review_markdown(queue: CohortFoundationReviewQueue) -> str:
    lines = ["| Record | Operation | Severity | Disposition | Issues |", "|---|---|---|---|---|"]
    lines.extend(f"| {item.record_id} | {item.operation} | {item.severity.value} | {item.disposition.value} | {', '.join(item.issue_codes) or 'none'} |" for item in queue.items)
    return "\n".join(lines) + "\n"


__all__ = ["export_cohort_foundation_frontier_canonical", "export_cohort_foundation_frontier_json", "export_cohort_foundation_frontier_manifest", "export_cohort_foundation_frontier_review_csv", "export_cohort_foundation_frontier_review_markdown"]
