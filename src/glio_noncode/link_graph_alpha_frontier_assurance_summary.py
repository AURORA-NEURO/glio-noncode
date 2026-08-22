"""Compact assurance summaries for dashboards and pull-request checks."""

from __future__ import annotations

from typing import Any

from .link_graph_alpha_frontier_assurance import LinkGraphAlphaFrontierAssuranceReport
from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport
from .link_graph_alpha_frontier_release_gate import LinkGraphAlphaFrontierReleaseGateReport


def summarize_link_graph_alpha_frontier_assurance(pipeline: LinkGraphAlphaFrontierPipelineReport, assurance: LinkGraphAlphaFrontierAssuranceReport, gate: LinkGraphAlphaFrontierReleaseGateReport) -> dict[str, Any]:
    return {
        "run_id": pipeline.run_id,
        "pipeline_accepted": pipeline.accepted,
        "assurance_accepted": assurance.accepted,
        "release_publishable": pipeline.release.publishable,
        "gate_publishable": gate.publishable,
        "blocking_failures": gate.blocking_failures,
        "stage_count": len(pipeline.stages),
        "record_count": len(pipeline.evaluation.rows),
        "review_count": pipeline.review_queue.review_count,
        "addresses": {
            "pipeline": pipeline.content_address,
            "assurance": assurance.content_address,
            "gate": gate.content_address,
        },
    }


def render_link_graph_alpha_frontier_assurance_summary(pipeline: LinkGraphAlphaFrontierPipelineReport, assurance: LinkGraphAlphaFrontierAssuranceReport, gate: LinkGraphAlphaFrontierReleaseGateReport) -> str:
    summary = summarize_link_graph_alpha_frontier_assurance(pipeline, assurance, gate)
    lines = ["Link graph alpha assurance", f"pipeline accepted: {summary['pipeline_accepted']}", f"assurance accepted: {summary['assurance_accepted']}", f"release publishable: {summary['release_publishable']}", f"gate publishable: {summary['gate_publishable']}", f"records: {summary['record_count']}", f"review entries: {summary['review_count']}"]
    if summary["blocking_failures"]:
        lines.append("blocking failures: " + ", ".join(summary["blocking_failures"]))
    else:
        lines.append("blocking failures: none")
    return "\n".join(lines)


__all__ = ["render_link_graph_alpha_frontier_assurance_summary", "summarize_link_graph_alpha_frontier_assurance"]
