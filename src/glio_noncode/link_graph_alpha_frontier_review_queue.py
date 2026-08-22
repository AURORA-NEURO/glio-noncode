"""Review queue construction ordered by boundary risk and declared controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_policy import LinkGraphAlphaFrontierDisposition, LinkGraphAlphaFrontierPolicyReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReviewEntry:
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
class LinkGraphAlphaFrontierReviewQueue:
    entries: tuple[LinkGraphAlphaFrontierReviewEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def review_count(self) -> int:
        return sum(item.disposition == LinkGraphAlphaFrontierDisposition.REVIEW.value for item in self.entries)

    def for_operation(self, operation: str) -> tuple[LinkGraphAlphaFrontierReviewEntry, ...]:
        return tuple(item for item in self.entries if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "review_count": self.review_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_review_queue(evaluation: LinkGraphAlphaFrontierEvaluation, policy: LinkGraphAlphaFrontierPolicyReport) -> LinkGraphAlphaFrontierReviewQueue:
    decisions = {item.record_id: item for item in policy.decisions}
    entries = []
    for row in evaluation.rows:
        decision = decisions[row.record_id]
        priority = 0 if row.observed_state == "out_of_domain" else 1 if row.observed_state in {"contradictory", "ambiguous", "abstained"} else 2 if row.observed_issue_codes else 3
        entries.append(LinkGraphAlphaFrontierReviewEntry(row.record_id, row.operation, priority, decision.disposition.value, row.observed_state, row.observed_issue_codes, decision.rationale))
    values = tuple(sorted(entries, key=lambda item: (item.priority, item.operation, item.record_id)))
    return LinkGraphAlphaFrontierReviewQueue(values, len(values) == len(evaluation.rows))


__all__ = ["LinkGraphAlphaFrontierReviewEntry", "LinkGraphAlphaFrontierReviewQueue", "build_link_graph_alpha_frontier_review_queue"]
