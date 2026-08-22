"""JSON, table, and manifest export helpers for causal frontier artifacts."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .causal_frontier_bundle import CausalFrontierReleaseBundle
from .causal_frontier_release import CausalFrontierReleaseManifest
from .causal_frontier_views import CausalFrontierReviewView
from .serialization import canonical_json, jsonable


def export_causal_frontier_json(value: Any, *, indent: int = 2) -> str:
    """Return deterministic, readable JSON for a causal artifact."""

    return json.dumps(jsonable(value), ensure_ascii=False, indent=indent, sort_keys=True) + "\n"


def export_causal_frontier_canonical(value: Any) -> str:
    return canonical_json(value)


def export_causal_frontier_manifest(
    bundle: CausalFrontierReleaseBundle,
    release: CausalFrontierReleaseManifest,
) -> dict[str, Any]:
    return {
        "manifest_type": "causal_frontier_release",
        "bundle": bundle.to_dict(),
        "release": release.to_dict(),
        "public_boundary": "public_aggregate_non_patient",
    }


def export_causal_frontier_review_csv(view: CausalFrontierReviewView) -> str:
    buffer = io.StringIO(newline="")
    fields = ("record_id", "operation", "role", "state", "accepted", "source_count", "issue_codes", "content_address")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in view.rows:
        writer.writerow({
            "record_id": row.record_id,
            "operation": row.operation,
            "role": row.role,
            "state": row.state,
            "accepted": str(row.accepted).lower(),
            "source_count": row.source_count,
            "issue_codes": ";".join(row.issue_codes),
            "content_address": row.content_address,
        })
    return buffer.getvalue()


__all__ = [
    "export_causal_frontier_canonical",
    "export_causal_frontier_json",
    "export_causal_frontier_manifest",
    "export_causal_frontier_review_csv",
]
