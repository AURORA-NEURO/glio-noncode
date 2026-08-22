"""Compact review views over operation, source, state, and issue dimensions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_review_queue import LinkGraphAlphaFrontierReviewQueue
from .link_graph_alpha_frontier_support import operation_counts, result_state_counts
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierOperationView:
    operation: str
    record_count: int
    state_counts: dict[str, int]
    review_count: int
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReviewView:
    fixture_id: str
    operations: tuple[LinkGraphAlphaFrontierOperationView, ...]
    total_records: int
    total_review: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def operation(self, operation: str) -> LinkGraphAlphaFrontierOperationView:
        for item in self.operations:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "operations": [item.to_dict() for item in self.operations], "total_records": self.total_records, "total_review": self.total_review, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_view(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation, queue: LinkGraphAlphaFrontierReviewQueue | None = None) -> LinkGraphAlphaFrontierReviewView:
    review = queue or LinkGraphAlphaFrontierReviewQueue((), False)
    operations = []
    for operation, count in operation_counts(fixture).items():
        rows = evaluation.by_operation(operation)
        entries = review.for_operation(operation)
        operations.append(LinkGraphAlphaFrontierOperationView(operation, count, result_state_counts(type("Rows", (), {"rows": rows})()), len(entries), tuple(sorted({source for row in rows for source in row.adapter.source_ids}))))
    values = tuple(operations)
    return LinkGraphAlphaFrontierReviewView(fixture.fixture_id, values, len(evaluation.rows), sum(item.review_count for item in values), all(item.record_count == 4 for item in values))


def filter_link_graph_alpha_frontier_review_queue(queue: LinkGraphAlphaFrontierReviewQueue, *, disposition: str | None = None, operation: str | None = None) -> tuple[LinkGraphAlphaFrontierReviewEntry, ...]:
    return tuple(item for item in queue.entries if (disposition is None or item.disposition == disposition) and (operation is None or item.operation == operation))


def link_graph_alpha_frontier_review_summary(queue: LinkGraphAlphaFrontierReviewQueue) -> dict[str, Any]:
    return {"entry_count": len(queue.entries), "review_count": queue.review_count, "by_priority": {str(priority): sum(item.priority == priority for item in queue.entries) for priority in sorted({item.priority for item in queue.entries})}}


__all__ = ["LinkGraphAlphaFrontierOperationView", "LinkGraphAlphaFrontierReviewView", "build_link_graph_alpha_frontier_view", "filter_link_graph_alpha_frontier_review_queue", "link_graph_alpha_frontier_review_summary"]
