"""Human-readable report facade for the alpha frontier runtime."""

from __future__ import annotations

from typing import Any

from .causal_alpha_frontier_runtime import CausalAlphaFrontierRuntimeReport


def causal_alpha_frontier_report(report: CausalAlphaFrontierRuntimeReport) -> dict[str, Any]:
    """Return a compact report while retaining addresses for drill-down."""

    return {
        "run_id": report.run_id,
        "fixture_id": report.fixture.fixture_id,
        "accepted": report.accepted,
        "stage_count": report.stage_count,
        "release_state": report.release.state,
        "record_count": len(report.fixture.records),
        "source_count": len(report.fixture.sources),
        "review_count": len(report.review.items),
        "allowed_count": report.operational.allowed_count,
        "quarantine_count": report.operational.quarantine_count,
        "artifact_count": len(report.artifacts.artifacts),
        "assurance_address": report.assurance.content_address,
        "content_address": report.content_address,
    }


__all__ = ["causal_alpha_frontier_report"]
