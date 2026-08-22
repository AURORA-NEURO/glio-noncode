"""Render pipeline and release summaries without losing machine values."""

from __future__ import annotations

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport
from .link_graph_alpha_frontier_reports import render_link_graph_alpha_frontier_pipeline_summary


def render_link_graph_alpha_frontier_pipeline_markdown(pipeline: LinkGraphAlphaFrontierPipelineReport) -> str:
    lines = [f"# {pipeline.run_id}", "", render_link_graph_alpha_frontier_pipeline_summary(pipeline.fixture, pipeline.metrics, pipeline.quality), "", "## Stages", "", "| Stage | Status | Inputs | Outputs |", "|---|---|---:|---:|"]
    lines.extend(f"| {stage.stage_id} | {stage.status} | {stage.input_count} | {stage.output_count} |" for stage in pipeline.stages)
    return "\n".join(lines) + "\n"


def render_link_graph_alpha_frontier_stage_lines(pipeline: LinkGraphAlphaFrontierPipelineReport) -> tuple[str, ...]:
    return tuple(f"{stage.stage_id}:{stage.status}:{stage.input_count}->{stage.output_count}" for stage in pipeline.stages)


__all__ = ["render_link_graph_alpha_frontier_pipeline_markdown", "render_link_graph_alpha_frontier_stage_lines"]
