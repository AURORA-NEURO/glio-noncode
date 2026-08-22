"""Safe query helpers over replay rows and source receipts."""

from __future__ import annotations

from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture


def query_link_graph_alpha_frontier_records(fixture: LinkGraphAlphaFrontierFixture, *, operation: str | None = None, role: str | None = None, context_key: str | None = None) -> tuple[dict[str, Any], ...]:
    rows = fixture.records
    if operation is not None:
        rows = tuple(item for item in rows if item.operation.value == operation)
    if role is not None:
        rows = tuple(item for item in rows if item.role.value == role)
    if context_key is not None:
        rows = tuple(item for item in rows if item.context_key == context_key)
    return tuple(item.to_dict() for item in rows)


def query_link_graph_alpha_frontier_results(evaluation: LinkGraphAlphaFrontierEvaluation, *, state: str | None = None, issue_code: str | None = None) -> tuple[dict[str, Any], ...]:
    rows = evaluation.rows
    if state is not None:
        rows = tuple(item for item in rows if item.observed_state == state)
    if issue_code is not None:
        rows = tuple(item for item in rows if issue_code in item.observed_issue_codes)
    return tuple(item.to_dict() for item in rows)


__all__ = ["query_link_graph_alpha_frontier_records", "query_link_graph_alpha_frontier_results"]
