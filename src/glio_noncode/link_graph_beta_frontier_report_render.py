"""Small deterministic renderers for beta review summaries."""

from __future__ import annotations

from typing import Any


def render_link_graph_beta_frontier_summary_markdown(summary: dict[str, Any]) -> str:
    lines = ["# Link graph beta frontier", "", f"- Fixture: `{summary.get('fixture_id', '')}`", f"- Records: `{summary.get('record_count', 0)}`", f"- Sources: `{summary.get('source_count', 0)}`", f"- Accepted: `{summary.get('accepted', False)}`", ""]
    return "\n".join(lines)


def render_link_graph_beta_frontier_table(rows: tuple[dict[str, Any], ...]) -> str:
    lines = ["record_id | operation | state", "--- | --- | ---"]
    lines.extend(f"{row.get('record_id', '')} | {row.get('operation', '')} | {row.get('observed_state', '')}" for row in rows)
    return "\n".join(lines) + "\n"


__all__ = ["render_link_graph_beta_frontier_summary_markdown", "render_link_graph_beta_frontier_table"]
