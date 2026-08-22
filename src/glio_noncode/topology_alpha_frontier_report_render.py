"""Compact text renderers for alpha validation and release summaries."""

from __future__ import annotations

from .topology_alpha_frontier_assurance import TopologyAlphaFrontierAssuranceReport
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport
from .topology_alpha_frontier_validation_report import TopologyAlphaFrontierValidationReport, build_topology_alpha_frontier_validation_report


def render_topology_alpha_frontier_pipeline_summary(pipeline: TopologyAlphaFrontierPipelineReport) -> str:
    lines = [f"run={pipeline.run_id}", f"accepted={str(pipeline.accepted).lower()}", f"records={len(pipeline.evaluation.rows)}", f"review={pipeline.review_queue.count}", f"stages={len(pipeline.stages)}", f"address={pipeline.content_address}"]
    lines.extend(f"stage.{item.stage_id}={item.status}" for item in pipeline.stages)
    return "\n".join(lines) + "\n"


def render_topology_alpha_frontier_validation_summary(report: TopologyAlphaFrontierValidationReport) -> str:
    lines = [f"report={report.report_id}", f"run={report.run_id}", f"accepted={str(report.accepted).lower()}"]
    lines.extend(f"{item.section_id}: {'pass' if item.passed else 'fail'} ({item.observed_count}/{item.expected_count})" for item in report.sections)
    return "\n".join(lines) + "\n"


def render_topology_alpha_frontier_assurance_summary(report: TopologyAlphaFrontierAssuranceReport) -> str:
    lines = [f"run={report.run_id}", f"accepted={str(report.accepted).lower()}", f"checks={len(report.checks)}"]
    lines.extend(f"{item.check_id}: {'pass' if item.passed else 'fail'}" for item in report.checks)
    return "\n".join(lines) + "\n"


def build_and_render_topology_alpha_frontier_validation(pipeline: TopologyAlphaFrontierPipelineReport) -> str:
    return render_topology_alpha_frontier_validation_summary(build_topology_alpha_frontier_validation_report(pipeline))


__all__ = ["build_and_render_topology_alpha_frontier_validation", "render_topology_alpha_frontier_assurance_summary", "render_topology_alpha_frontier_pipeline_summary", "render_topology_alpha_frontier_validation_summary"]
