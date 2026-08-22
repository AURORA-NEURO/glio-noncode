"""Canonical JSON and CSV exports for the C05-C08 review package."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .serialization import jsonable
from .workspace_beta_frontier_bundle import BetaFrontierReleaseBundle
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_metrics import BetaFrontierMetricsReport
from .workspace_beta_frontier_public_data import BetaFrontierFixture
from .workspace_beta_frontier_release import BetaFrontierReleaseManifest
from .workspace_beta_frontier_views import BetaFrontierReviewView


def export_beta_frontier_json(value: Any) -> str:
    """Serialize a package object using the repository canonical encoder."""

    return json.dumps(jsonable(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def export_beta_frontier_canonical(value: Any) -> dict[str, Any]:
    """Return a JSON-compatible mapping for API consumers."""

    payload = jsonable(value)
    return payload if isinstance(payload, dict) else {"value": payload}


def export_beta_frontier_manifest(
    fixture: BetaFrontierFixture,
    evaluation: BetaFrontierEvaluation,
    metrics: BetaFrontierMetricsReport,
    bundle: BetaFrontierReleaseBundle,
    release: BetaFrontierReleaseManifest,
) -> dict[str, Any]:
    """Compose the compact release manifest without embedding every row."""

    return {
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "evaluation_address": evaluation.content_address,
        "metrics_address": metrics.content_address,
        "bundle_address": bundle.content_address,
        "release_address": release.content_address,
        "release_state": release.state.value,
        "public_boundary": fixture.evidence_boundary,
        "operation_count": len({item.operation for item in evaluation.executions}),
        "record_count": len(evaluation.executions),
    }


def export_beta_frontier_review_csv(view: BetaFrontierReviewView) -> str:
    """Export stable review fields for spreadsheet and issue workflows."""

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("row_id", "record_id", "operation", "role", "state", "decision", "issue_codes", "source_ids", "notes", "content_address"))
    for row in view.rows:
        writer.writerow((row.row_id, row.record_id, row.operation, row.role, row.state, row.decision, ";".join(row.issue_codes), ";".join(row.source_ids), row.notes, row.content_address))
    return output.getvalue()


__all__ = ["export_beta_frontier_canonical", "export_beta_frontier_json", "export_beta_frontier_manifest", "export_beta_frontier_review_csv"]
