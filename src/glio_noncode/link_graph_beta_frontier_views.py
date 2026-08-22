"""Sanitized review view for beta frontier records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture
from .link_graph_beta_frontier_review_queue import LinkGraphBetaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReviewView:
    fixture_id: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "columns": self.columns, "rows": self.rows, "row_count": len(self.rows), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_view(fixture: LinkGraphBetaFrontierFixture, evaluation: LinkGraphBetaFrontierEvaluation, queue: LinkGraphBetaFrontierReviewQueue) -> LinkGraphBetaFrontierReviewView:
    columns = ("record_id", "operation", "role", "state", "disposition", "issue_codes", "priority")
    rows = tuple({"record_id": row.record_id, "operation": row.operation, "role": row.role, "state": row.observed_state, "disposition": next(item.disposition for item in queue.entries if item.record_id == row.record_id), "issue_codes": row.observed_issue_codes, "priority": next(item.priority for item in queue.entries if item.record_id == row.record_id)} for row in evaluation.rows)
    return LinkGraphBetaFrontierReviewView(fixture.fixture_id, columns, rows, len(rows) == len(evaluation.rows) and queue.accepted)


def filter_link_graph_beta_frontier_review_queue(queue: LinkGraphBetaFrontierReviewQueue, *, operation: str | None = None, disposition: str | None = None) -> tuple[Any, ...]:
    values = queue.entries
    if operation is not None:
        values = tuple(item for item in values if item.operation == operation)
    if disposition is not None:
        values = tuple(item for item in values if item.disposition == disposition)
    return values


__all__ = ["LinkGraphBetaFrontierReviewView", "build_link_graph_beta_frontier_view", "filter_link_graph_beta_frontier_review_queue"]
