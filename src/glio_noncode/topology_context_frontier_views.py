"""Review view projections with explicit state and issue columns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    state: str
    issue_count: int
    candidate_count: int
    result_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierReviewView:
    rows: tuple[TopologyContextFrontierReviewRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def review_count(self) -> int:
        return sum(item.state != "supported" for item in self.rows)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "rows": [item.to_dict() for item in self.rows],
            "accepted": self.accepted,
            "review_count": self.review_count,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_view(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierReviewView:
    rows = tuple(
        TopologyContextFrontierReviewRow(
            item.record_id,
            item.operation,
            item.role,
            item.observed_state,
            len(item.observed_issue_codes),
            len(item.adapter.measurements.get("interaction_ids", ()))
            + int(item.adapter.measurements.get("cluster_count", 0)),
            item.adapter.content_address,
        )
        for item in evaluation.rows
    )
    return TopologyContextFrontierReviewView(rows, all(bool(item.record_id) for item in rows))


__all__ = [
    "TopologyContextFrontierReviewRow",
    "TopologyContextFrontierReviewView",
    "build_topology_context_frontier_view",
]
