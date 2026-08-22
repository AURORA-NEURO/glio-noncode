"""Review queue built from ambiguous, partial, and foreign rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierQueueItem:
    queue_id: str
    record_id: str
    priority: str
    state: str
    reason: str
    result_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierReviewQueue:
    items: tuple[TopologyContextFrontierQueueItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def count(self) -> int:
        return len(self.items)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "items": [item.to_dict() for item in self.items],
            "accepted": self.accepted,
            "count": self.count,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_review_queue(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierReviewQueue:
    items = tuple(
        TopologyContextFrontierQueueItem(
            f"queue-{item.record_id}",
            item.record_id,
            "high" if item.observed_state in {"out_of_domain", "invalid"} else "normal",
            item.observed_state,
            ",".join(item.observed_issue_codes) or f"state:{item.observed_state}",
            item.adapter.content_address,
        )
        for item in evaluation.rows
        if item.observed_state != "supported"
    )
    return TopologyContextFrontierReviewQueue(items, all(bool(item.reason) for item in items))


__all__ = [
    "TopologyContextFrontierQueueItem",
    "TopologyContextFrontierReviewQueue",
    "build_topology_context_frontier_review_queue",
]
