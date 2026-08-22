"""Canonical JSON and CSV exports for the collaboration frontier."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .serialization import jsonable
from .workspace_gamma_frontier_bundle import GammaFrontierEvidenceBundle
from .workspace_gamma_frontier_metrics import GammaFrontierMetricsReport
from .workspace_gamma_frontier_release import GammaFrontierReleaseManifest
from .workspace_gamma_frontier_views import GammaFrontierReviewView


def export_gamma_frontier_json(value: Any) -> str:
    """Serialize any public package object using the canonical encoder."""

    return json.dumps(jsonable(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def export_gamma_frontier_canonical(value: Any) -> dict[str, Any]:
    """Return a JSON-compatible mapping for API callers."""

    payload = jsonable(value)
    return payload if isinstance(payload, dict) else {"value": payload}


def export_gamma_frontier_manifest(
    metrics: GammaFrontierMetricsReport,
    bundle: GammaFrontierEvidenceBundle,
    release: GammaFrontierReleaseManifest,
) -> dict[str, Any]:
    """Compose the compact address-only manifest."""

    return {
        "fixture_id": bundle.fixture_id,
        "metrics_address": metrics.content_address,
        "bundle_address": bundle.content_address,
        "release_address": release.content_address,
        "release_state": release.state.value,
        "entry_count": len(bundle.entries),
        "metric_count": len(metrics.metrics),
        "research_boundary": bundle.research_boundary,
    }


def export_gamma_frontier_review_csv(view: GammaFrontierReviewView) -> str:
    """Export stable review fields for issue and spreadsheet workflows."""

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "row_id",
            "record_id",
            "operation",
            "role",
            "state",
            "decision",
            "issue_codes",
            "source_ids",
            "notes",
            "content_address",
        )
    )
    for row in view.rows:
        writer.writerow(
            (
                row.row_id,
                row.record_id,
                row.operation,
                row.role,
                row.state,
                row.decision,
                ";".join(row.issue_codes),
                ";".join(row.source_ids),
                row.notes,
                row.content_address,
            )
        )
    return output.getvalue()


__all__ = [
    "export_gamma_frontier_canonical",
    "export_gamma_frontier_json",
    "export_gamma_frontier_manifest",
    "export_gamma_frontier_review_csv",
]
