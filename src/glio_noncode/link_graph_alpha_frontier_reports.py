"""Human-readable summaries for operation and release review."""

from __future__ import annotations

from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_metrics import LinkGraphAlphaFrontierMetrics
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_quality_gate import LinkGraphAlphaFrontierQualityReport


def render_link_graph_alpha_frontier_evaluation_summary(evaluation: LinkGraphAlphaFrontierEvaluation) -> str:
    lines = ["Link graph alpha frontier evaluation", f"accepted: {evaluation.accepted}", f"state matches: {evaluation.state_match_count}/{len(evaluation.rows)}", f"issue matches: {evaluation.issue_match_count}/{len(evaluation.rows)}"]
    lines.extend(f"- {row.record_id}: {row.observed_state} ({', '.join(row.observed_issue_codes) or 'no issues'})" for row in evaluation.rows)
    return "\n".join(lines)


def render_link_graph_alpha_frontier_pipeline_summary(fixture: LinkGraphAlphaFrontierFixture, metrics: LinkGraphAlphaFrontierMetrics, quality: LinkGraphAlphaFrontierQualityReport) -> str:
    lines = ["Link graph alpha frontier pipeline", f"fixture: {fixture.fixture_id}", f"records: {len(fixture.records)}", f"sources: {len(fixture.sources)}", f"state accuracy: {metrics.state_accuracy:.3f}", f"issue accuracy: {metrics.issue_accuracy:.3f}", f"quality: {quality.accepted}"]
    lines.extend(f"- {item.operation}: {item.record_count} records, {item.state_match_count} state matches" for item in metrics.operations)
    return "\n".join(lines)


def link_graph_alpha_frontier_summary_payload(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation, metrics: LinkGraphAlphaFrontierMetrics) -> dict[str, Any]:
    return {"fixture_id": fixture.fixture_id, "record_count": len(fixture.records), "source_count": len(fixture.sources), "accepted": evaluation.accepted, "state_accuracy": metrics.state_accuracy, "issue_accuracy": metrics.issue_accuracy, "state_counts": metrics.state_counts}


__all__ = ["link_graph_alpha_frontier_summary_payload", "render_link_graph_alpha_frontier_evaluation_summary", "render_link_graph_alpha_frontier_pipeline_summary"]
