"""Canonical JSON and CSV exports for C01-C04 evidence review."""

from __future__ import annotations

import json
from typing import Any

from .causal_foundation_frontier_artifacts import CausalFoundationFrontierArtifactInventory
from .causal_foundation_frontier_runtime import CausalFoundationFrontierRuntimeReport
from .causal_foundation_frontier_views import CausalFoundationFrontierReviewView


def causal_foundation_frontier_export_payload(runtime: CausalFoundationFrontierRuntimeReport) -> dict[str, Any]:
    return {"release": runtime.release.to_dict(), "bundle": runtime.bundle.to_dict(), "evaluation": runtime.evaluation.to_dict(), "metrics": runtime.metrics.to_dict(), "quality_gate": runtime.gate.to_dict(), "review": runtime.review.to_dict(), "artifacts": runtime.artifacts.to_dict(), "accepted": runtime.accepted}


def causal_foundation_frontier_export_json(runtime: CausalFoundationFrontierRuntimeReport) -> str:
    return json.dumps(causal_foundation_frontier_export_payload(runtime), sort_keys=True, default=str, indent=2) + "\n"


def causal_foundation_frontier_export_manifest(inventory: CausalFoundationFrontierArtifactInventory) -> str:
    return json.dumps(inventory.to_dict(), sort_keys=True, default=str, indent=2) + "\n"


def causal_foundation_frontier_export_review_csv(view: CausalFoundationFrontierReviewView) -> str:
    return view.to_csv()


def causal_foundation_frontier_export_review_markdown(view: CausalFoundationFrontierReviewView) -> str:
    lines = ["# Causal foundation review", "", " | ".join(view.columns), " | ".join("---" for _ in view.columns)]
    for row in view.rows:
        values = row.to_dict(False)
        lines.append(" | ".join(str(values.get(column, "")).replace("|", "\\|") for column in view.columns))
    return "\n".join(lines) + "\n"


__all__ = ["causal_foundation_frontier_export_json", "causal_foundation_frontier_export_manifest", "causal_foundation_frontier_export_payload", "causal_foundation_frontier_export_review_csv", "causal_foundation_frontier_export_review_markdown"]
