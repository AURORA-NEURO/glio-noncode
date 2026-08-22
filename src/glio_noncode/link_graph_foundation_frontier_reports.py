"""Compact reports for review and release handoff."""

from __future__ import annotations

from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_metrics import LinkGraphFoundationFrontierMetrics
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture


def render_link_graph_foundation_frontier_evaluation_summary(evaluation: LinkGraphFoundationFrontierEvaluation) -> str:
    return "\n".join(("Link graph foundation evaluation", f"accepted: {evaluation.accepted}", f"state matches: {evaluation.state_match_count}/{len(evaluation.rows)}", f"issue matches: {evaluation.issue_match_count}/{len(evaluation.rows)}", *[f"- {row.record_id}: {row.observed_state} ({', '.join(row.observed_issue_codes) or 'none'})" for row in evaluation.rows]))


def link_graph_foundation_frontier_summary_payload(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation, metrics: LinkGraphFoundationFrontierMetrics) -> dict[str, Any]:
    return {"fixture_id": fixture.fixture_id, "record_count": len(fixture.records), "source_count": len(fixture.sources), "accepted": evaluation.accepted, "state_accuracy": metrics.state_accuracy, "state_counts": metrics.state_counts, "issue_counts": metrics.issue_counts}


__all__ = ["link_graph_foundation_frontier_summary_payload", "render_link_graph_foundation_frontier_evaluation_summary"]
