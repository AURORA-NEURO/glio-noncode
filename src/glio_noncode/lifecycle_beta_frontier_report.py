"""Markdown report assembly for release review."""

from __future__ import annotations

from .lifecycle_beta_frontier_exports import render_lifecycle_beta_frontier_review_markdown
from .lifecycle_beta_frontier_runtime import LifecycleBetaFrontierRuntimeReport
from .lifecycle_beta_frontier_summary import build_lifecycle_beta_frontier_summary


def render_lifecycle_beta_frontier_report(runtime: LifecycleBetaFrontierRuntimeReport) -> str:
    summary = build_lifecycle_beta_frontier_summary(runtime.fixture, runtime.evaluation, runtime.metrics, runtime.quality)
    view = __import__("glio_noncode.lifecycle_beta_frontier_views", fromlist=["build_lifecycle_beta_frontier_view"]).build_lifecycle_beta_frontier_view(runtime.evaluation)
    lines = [
        "# Lifecycle Beta Frontier Report",
        "",
        f"Run: {runtime.run_id}",
        f"Accepted: {runtime.accepted}",
        f"Records: {summary.record_count}",
        f"Positive rows: {summary.positive_count}",
        f"Control rows: {summary.control_count}",
        f"Evaluation failures: {summary.failed_check_count}",
        "",
        render_lifecycle_beta_frontier_review_markdown(view, runtime.release),
    ]
    return "\n".join(lines)


__all__ = ["render_lifecycle_beta_frontier_report"]
