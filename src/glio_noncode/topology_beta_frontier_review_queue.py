"""Review queue preserving every control and non-supported state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierReviewItem:
    review_id: str
    record_id: str
    operation: str
    priority: str
    state: str
    issue_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    rationale: str
    status: str = "open"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierReviewQueue:
    items: tuple[TopologyBetaFrontierReviewItem, ...]
    count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_priority(self, priority: str) -> tuple[TopologyBetaFrontierReviewItem, ...]:
        return tuple(item for item in self.items if item.priority == priority)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"items": [item.to_dict() for item in self.items], "count": self.count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_review_queue(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierReviewQueue:
    items = []
    for row in evaluation.rows:
        if row.role == "control" or row.observed_state != "supported":
            priority = "high" if row.observed_state in {"out_of_domain", "ambiguous"} else "medium"
            items.append(TopologyBetaFrontierReviewItem(f"review-{row.record_id}", row.record_id, row.operation, priority, row.observed_state, row.observed_issue_codes, row.adapter.evidence_ids, "control or non-supported state requires explicit review"))
    values = tuple(items)
    return TopologyBetaFrontierReviewQueue(values, len(values), len(values) == 12 and all(item.status == "open" for item in values))


__all__ = ["TopologyBetaFrontierReviewItem", "TopologyBetaFrontierReviewQueue", "build_topology_beta_frontier_review_queue"]
