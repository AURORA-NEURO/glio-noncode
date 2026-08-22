"""JSON-safe export helpers for beta frontier reports."""

from __future__ import annotations

import json
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture


def serialize_link_graph_beta_frontier_record(record: Any) -> dict[str, Any]:
    return record.to_dict()


def serialize_link_graph_beta_frontier_rows(evaluation: LinkGraphBetaFrontierEvaluation) -> tuple[dict[str, Any], ...]:
    return tuple(row.to_dict() for row in evaluation.rows)


def link_graph_beta_frontier_fixture_json(fixture: LinkGraphBetaFrontierFixture | None = None) -> str:
    return json.dumps((fixture or default_link_graph_beta_frontier_fixture()).to_dict(), sort_keys=True, indent=2)


def render_link_graph_beta_frontier_review_markdown(rows: tuple[dict[str, Any], ...]) -> str:
    lines = ["# Link graph beta frontier review", "", "| record_id | operation | state | issues |", "|---|---|---|---|"]
    lines.extend(f"| {row['record_id']} | {row['operation']} | {row['observed_state']} | {', '.join(row['observed_issue_codes']) or 'none'} |" for row in rows)
    return "\n".join(lines) + "\n"


__all__ = ["link_graph_beta_frontier_fixture_json", "render_link_graph_beta_frontier_review_markdown", "serialize_link_graph_beta_frontier_record", "serialize_link_graph_beta_frontier_rows"]
