"""Safety assertions for boundary, serialization, and review handling."""

from __future__ import annotations

from typing import Any

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport


def link_graph_alpha_frontier_safe_summary(pipeline: LinkGraphAlphaFrontierPipelineReport) -> dict[str, Any]:
    """Return a summary containing only bounded, non-patient fields."""

    return {
        "run_id": pipeline.run_id,
        "fixture_id": pipeline.fixture.fixture_id,
        "boundary": pipeline.fixture.boundary,
        "record_count": len(pipeline.fixture.records),
        "source_count": len(pipeline.fixture.sources),
        "state_counts": pipeline.metrics.state_counts,
        "issue_counts": pipeline.metrics.issue_counts,
        "failed_stages": pipeline.failed_stages,
        "accepted": pipeline.accepted,
    }


def link_graph_alpha_frontier_has_context_gate(pipeline: LinkGraphAlphaFrontierPipelineReport) -> bool:
    return all(row.observed_state == "out_of_domain" for row in pipeline.evaluation.rows if row.record_id.endswith("C3"))


def link_graph_alpha_frontier_has_review_closure(pipeline: LinkGraphAlphaFrontierPipelineReport) -> bool:
    return len(pipeline.review_queue.entries) == len(pipeline.evaluation.rows) and all(item.rationale for item in pipeline.review_queue.entries)


def link_graph_alpha_frontier_safety_checks(pipeline: LinkGraphAlphaFrontierPipelineReport) -> dict[str, bool]:
    return {
        "aggregate_boundary": pipeline.fixture.boundary == "public_aggregate_non_patient",
        "context_gate": link_graph_alpha_frontier_has_context_gate(pipeline),
        "review_closure": link_graph_alpha_frontier_has_review_closure(pipeline),
        "release_gate": pipeline.release.publishable,
    }


__all__ = ["link_graph_alpha_frontier_has_context_gate", "link_graph_alpha_frontier_has_review_closure", "link_graph_alpha_frontier_safe_summary", "link_graph_alpha_frontier_safety_checks"]
