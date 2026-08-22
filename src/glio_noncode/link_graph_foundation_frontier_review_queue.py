"""Ordered review queue for baseline controls and boundary rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_policy import LinkGraphFoundationFrontierPolicyReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReviewEntry:
    record_id: str
    operation: str
    priority: int
    disposition: str
    state: str
    issue_codes: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReviewQueue:
    entries: tuple[LinkGraphFoundationFrontierReviewEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def review_count(self) -> int:
        return sum(item.disposition == "review" for item in self.entries)

    def for_operation(self, operation: str) -> tuple[LinkGraphFoundationFrontierReviewEntry, ...]:
        return tuple(item for item in self.entries if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "review_count": self.review_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_review_queue(evaluation: LinkGraphFoundationFrontierEvaluation, policy: LinkGraphFoundationFrontierPolicyReport) -> LinkGraphFoundationFrontierReviewQueue:
    decisions = {item.record_id: item for item in policy.decisions}
    entries = tuple(sorted((LinkGraphFoundationFrontierReviewEntry(row.record_id, row.operation, 0 if row.observed_state == "out_of_domain" else 1 if row.observed_issue_codes else 2, decisions[row.record_id].disposition.value, row.observed_state, row.observed_issue_codes, decisions[row.record_id].rationale) for row in evaluation.rows), key=lambda item: (item.priority, item.operation, item.record_id)))
    return LinkGraphFoundationFrontierReviewQueue(entries, len(entries) == len(evaluation.rows))


__all__ = ["LinkGraphFoundationFrontierReviewEntry", "LinkGraphFoundationFrontierReviewQueue", "build_link_graph_foundation_frontier_review_queue"]
