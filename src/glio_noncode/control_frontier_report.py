"""Markdown report assembly for control frontier runtime review."""

from __future__ import annotations

from .control_frontier_runtime import ControlFrontierRuntimeReport
from .control_frontier_summary import build_control_frontier_summary
from .control_frontier_views import build_control_frontier_view
from .control_frontier_exports import render_control_frontier_review_markdown


def render_control_frontier_report(runtime: ControlFrontierRuntimeReport) -> str:
    summary = build_control_frontier_summary(runtime.fixture, runtime.evaluation, runtime.metrics, runtime.quality)
    view = build_control_frontier_view(runtime.evaluation)
    return "\n".join((
        "# Control frontier report",
        "",
        f"Run: `{runtime.run_id}`",
        f"Accepted: `{runtime.accepted}`",
        f"Records: `{summary.record_count}`",
        f"Positive rows: `{summary.positive_count}`",
        f"Control rows: `{summary.control_count}`",
        f"Quality gate: `{summary.quality_accepted}`",
        "",
        render_control_frontier_review_markdown(view),
    ))


__all__ = ["render_control_frontier_report"]
