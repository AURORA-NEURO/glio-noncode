"""Compact operation views and review filters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture
from .link_graph_foundation_frontier_review_queue import LinkGraphFoundationFrontierReviewQueue
from .link_graph_foundation_frontier_support import state_counts
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierOperationView:
    operation: str
    record_count: int
    state_counts: dict[str, int]
    review_count: int
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReviewView:
    fixture_id: str
    operations: tuple[LinkGraphFoundationFrontierOperationView, ...]
    total_records: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def operation(self, operation: str) -> LinkGraphFoundationFrontierOperationView:
        for item in self.operations:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "operations": [item.to_dict() for item in self.operations], "total_records": self.total_records, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_view(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation, queue: LinkGraphFoundationFrontierReviewQueue) -> LinkGraphFoundationFrontierReviewView:
    operations = tuple(LinkGraphFoundationFrontierOperationView(operation.value, len(rows := evaluation.by_operation(operation.value)), state_counts(type("Rows", (), {"rows": rows})()), len(queue.for_operation(operation.value)), tuple(sorted({source for row in rows for source in row.adapter.source_ids}))) for operation in __import__("glio_noncode.link_graph_foundation_frontier_public_data", fromlist=["LinkGraphFoundationFrontierOperation"]).LinkGraphFoundationFrontierOperation)
    return LinkGraphFoundationFrontierReviewView(fixture.fixture_id, operations, len(evaluation.rows), all(item.record_count == 4 for item in operations))


def filter_link_graph_foundation_frontier_review_queue(queue: LinkGraphFoundationFrontierReviewQueue, *, operation: str | None = None, disposition: str | None = None) -> tuple[LinkGraphFoundationFrontierReviewEntry, ...]:
    return tuple(item for item in queue.entries if (operation is None or item.operation == operation) and (disposition is None or item.disposition == disposition))


def link_graph_foundation_frontier_review_summary(queue: LinkGraphFoundationFrontierReviewQueue) -> dict[str, Any]:
    return {"entry_count": len(queue.entries), "review_count": queue.review_count, "priority_counts": {str(priority): sum(item.priority == priority for item in queue.entries) for priority in sorted({item.priority for item in queue.entries})}}


__all__ = ["LinkGraphFoundationFrontierOperationView", "LinkGraphFoundationFrontierReviewView", "build_link_graph_foundation_frontier_view", "filter_link_graph_foundation_frontier_review_queue", "link_graph_foundation_frontier_review_summary"]
