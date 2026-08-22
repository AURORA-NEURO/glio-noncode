"""Markdown rendering for the baseline pipeline."""

from __future__ import annotations

from .link_graph_foundation_frontier_pipeline import LinkGraphFoundationFrontierPipelineReport
from .link_graph_foundation_frontier_reports import render_link_graph_foundation_frontier_evaluation_summary


def render_link_graph_foundation_frontier_pipeline_markdown(pipeline: LinkGraphFoundationFrontierPipelineReport) -> str:
    lines = [f"# {pipeline.run_id}", "", render_link_graph_foundation_frontier_evaluation_summary(pipeline.evaluation), "", "## Stages", "", "| Stage | Status | Inputs | Outputs |", "|---|---|---:|---:|"]
    lines.extend(f"| {item.stage_id} | {item.status} | {item.input_count} | {item.output_count} |" for item in pipeline.stages)
    return "\n".join(lines) + "\n"


__all__ = ["render_link_graph_foundation_frontier_pipeline_markdown"]
