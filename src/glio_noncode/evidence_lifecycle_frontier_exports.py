"""Stable JSON, canonical, manifest, and CSV exports for Domain 14."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .evidence_lifecycle_frontier_bundle import EvidenceLifecycleReleaseBundle
from .evidence_lifecycle_frontier_release import EvidenceLifecycleReleaseManifest
from .evidence_lifecycle_frontier_views import EvidenceLifecycleReviewView


def export_evidence_lifecycle_json(value: Any) -> str:
    body = value.to_dict() if hasattr(value, "to_dict") else value
    return json.dumps(body, indent=2, sort_keys=True, default=str) + "\n"


def export_evidence_lifecycle_canonical(value: Any) -> str:
    body = value.to_dict() if hasattr(value, "to_dict") else value
    return json.dumps(body, separators=(",", ":"), sort_keys=True, default=str)


def export_evidence_lifecycle_manifest(bundle: EvidenceLifecycleReleaseBundle, release: EvidenceLifecycleReleaseManifest) -> dict[str, Any]:
    return {"bundle_id": bundle.bundle_id, "release_id": release.release_id, "release_state": release.state.value, "accepted": release.accepted, "public_boundary": "public_aggregate_non_patient", "content_address": release.content_address}


def export_evidence_lifecycle_review_csv(view: EvidenceLifecycleReviewView) -> str:
    stream = io.StringIO()
    fields = ("record_id", "operation", "role", "state", "accepted", "issue_codes", "source_ids", "release_state")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in view.rows:
        writer.writerow({"record_id": row.record_id, "operation": row.operation.value, "role": row.role.value, "state": row.state, "accepted": row.accepted, "issue_codes": "|".join(row.issue_codes), "source_ids": "|".join(row.source_ids), "release_state": row.release_state})
    return stream.getvalue()


__all__ = ["export_evidence_lifecycle_canonical", "export_evidence_lifecycle_json", "export_evidence_lifecycle_manifest", "export_evidence_lifecycle_review_csv"]
