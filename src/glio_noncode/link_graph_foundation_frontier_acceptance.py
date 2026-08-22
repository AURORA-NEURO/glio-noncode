"""Acceptance gates for the C01-C04 release."""

from __future__ import annotations

from .link_graph_foundation_frontier_pipeline import LinkGraphFoundationFrontierPipelineReport
from .link_graph_foundation_frontier_support import LinkGraphFoundationFrontierReport, check, report


def evaluate_link_graph_foundation_frontier_acceptance(pipeline: LinkGraphFoundationFrontierPipelineReport) -> LinkGraphFoundationFrontierReport:
    checks = (check("pipeline", pipeline.accepted, "all pipeline stages pass"), check("release", pipeline.release.publishable, "release is publishable"), check("bundle", pipeline.bundle.accepted, "bundle is closed"), check("artifacts", pipeline.artifacts.accepted, "artifacts are closed"), check("review", len(pipeline.review_queue.entries) == len(pipeline.evaluation.rows), "review queue covers all rows"))
    return report("link-graph-foundation-frontier-acceptance", checks)


__all__ = ["evaluate_link_graph_foundation_frontier_acceptance"]
