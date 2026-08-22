"""Stable JSON, canonical, manifest, and review CSV exports."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .serialization import canonical_json
from .workspace_frontier_release import WorkspaceFrontierReleaseManifest
from .workspace_frontier_runtime import WorkspaceFrontierRuntimeReport
from .workspace_frontier_views import WorkspaceFrontierReviewView


def export_workspace_frontier_json(value: Any) -> str:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def export_workspace_frontier_canonical(value: Any) -> str:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    return canonical_json(payload)


def export_workspace_frontier_manifest(runtime: WorkspaceFrontierRuntimeReport, release: WorkspaceFrontierReleaseManifest) -> dict[str, Any]:
    return {
        "fixture_id": runtime.fixture_id,
        "run_id": runtime.run_id,
        "public_boundary": runtime.bundle.public_boundary,
        "release_id": release.release_id,
        "release_state": release.state.value,
        "accepted": release.accepted,
        "runtime_address": runtime.content_address,
        "release_address": release.content_address,
        "stage_count": len(runtime.stages),
    }


def export_workspace_frontier_review_csv(view: WorkspaceFrontierReviewView) -> str:
    output = io.StringIO()
    fields = ("record_id", "operation", "role", "state", "issue_codes", "decision", "publishable", "source_count", "notes", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in view.rows:
        writer.writerow({
            "record_id": row.record_id,
            "operation": row.operation,
            "role": row.role,
            "state": row.state,
            "issue_codes": ";".join(row.issue_codes),
            "decision": row.decision,
            "publishable": str(row.publishable).lower(),
            "source_count": row.source_count,
            "notes": row.notes,
            "content_address": row.content_address,
        })
    return output.getvalue()


__all__ = ["export_workspace_frontier_canonical", "export_workspace_frontier_json", "export_workspace_frontier_manifest", "export_workspace_frontier_review_csv"]
