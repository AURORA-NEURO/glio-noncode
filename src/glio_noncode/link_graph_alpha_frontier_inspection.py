"""Inspection helpers for operators and automated review surfaces."""

from __future__ import annotations

from typing import Any

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport


def inspect_link_graph_alpha_frontier_pipeline(pipeline: LinkGraphAlphaFrontierPipelineReport) -> dict[str, Any]:
    return {
        "run_id": pipeline.run_id,
        "accepted": pipeline.accepted,
        "fixture_id": pipeline.fixture.fixture_id,
        "fixture_version": pipeline.fixture.version,
        "boundary": pipeline.fixture.boundary,
        "record_count": len(pipeline.fixture.records),
        "source_count": len(pipeline.fixture.sources),
        "state_counts": pipeline.metrics.state_counts,
        "issue_counts": pipeline.metrics.issue_counts,
        "review_count": pipeline.review_queue.review_count,
        "failed_stages": pipeline.failed_stages,
        "content_address": pipeline.content_address,
    }


def inspect_link_graph_alpha_frontier_operation(pipeline: LinkGraphAlphaFrontierPipelineReport, operation: str) -> dict[str, Any]:
    metric = pipeline.metrics.for_operation(operation)
    view = pipeline.view.operation(operation)
    return {
        "operation": operation,
        "record_count": metric.record_count,
        "positive_count": metric.positive_count,
        "control_count": metric.control_count,
        "state_match_count": metric.state_match_count,
        "issue_match_count": metric.issue_match_count,
        "state_counts": view.state_counts,
        "review_count": view.review_count,
        "source_ids": view.source_ids,
    }


def inspect_link_graph_alpha_frontier_record(pipeline: LinkGraphAlphaFrontierPipelineReport, record_id: str) -> dict[str, Any]:
    for row in pipeline.evaluation.rows:
        if row.record_id == record_id:
            return {
                "record_id": row.record_id,
                "operation": row.operation,
                "role": row.role,
                "expected_state": row.expected_state,
                "observed_state": row.observed_state,
                "expected_issue_codes": row.expected_issue_codes,
                "observed_issue_codes": row.observed_issue_codes,
                "measurements": row.adapter.measurements,
                "evidence_ids": row.adapter.evidence_ids,
                "content_address": row.adapter.content_address,
            }
    raise KeyError(record_id)


__all__ = ["inspect_link_graph_alpha_frontier_operation", "inspect_link_graph_alpha_frontier_pipeline", "inspect_link_graph_alpha_frontier_record"]
