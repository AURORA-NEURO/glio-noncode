"""Safe record and result queries."""

from __future__ import annotations

from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture


def query_link_graph_foundation_frontier_records(fixture: LinkGraphFoundationFrontierFixture, *, operation: str | None = None, role: str | None = None) -> tuple[dict[str, Any], ...]:
    rows = fixture.records
    if operation is not None:
        rows = tuple(item for item in rows if item.operation.value == operation)
    if role is not None:
        rows = tuple(item for item in rows if item.role.value == role)
    return tuple(item.to_dict() for item in rows)


def query_link_graph_foundation_frontier_results(evaluation: LinkGraphFoundationFrontierEvaluation, *, state: str | None = None, issue_code: str | None = None) -> tuple[dict[str, Any], ...]:
    rows = evaluation.rows
    if state is not None:
        rows = tuple(item for item in rows if item.observed_state == state)
    if issue_code is not None:
        rows = tuple(item for item in rows if issue_code in item.observed_issue_codes)
    return tuple(item.to_dict() for item in rows)


__all__ = ["query_link_graph_foundation_frontier_records", "query_link_graph_foundation_frontier_results"]
