"""Review queue for beta controls, abstentions, contradictions, and foreign rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_policy import LinkGraphBetaFrontierDisposition, LinkGraphBetaFrontierPolicyReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReviewEntry:
    record_id: str
    operation: str
    state: str
    disposition: str
    issue_codes: tuple[str, ...]
    priority: int
    review_reason: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReviewQueue:
    entries: tuple[LinkGraphBetaFrontierReviewEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[LinkGraphBetaFrontierReviewEntry, ...]:
        return tuple(item for item in self.entries if item.operation == operation)

    def for_disposition(self, disposition: str) -> tuple[LinkGraphBetaFrontierReviewEntry, ...]:
        return tuple(item for item in self.entries if item.disposition == disposition)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "entry_count": len(self.entries), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_review_queue(evaluation: LinkGraphBetaFrontierEvaluation, policy: LinkGraphBetaFrontierPolicyReport) -> LinkGraphBetaFrontierReviewQueue:
    entries = []
    for index, decision in enumerate(policy.decisions):
        row = next(item for item in evaluation.rows if item.record_id == decision.record_id)
        if decision.disposition is LinkGraphBetaFrontierDisposition.RETAIN:
            priority = 3
        elif decision.disposition is LinkGraphBetaFrontierDisposition.REVIEW:
            priority = 1
        elif decision.disposition is LinkGraphBetaFrontierDisposition.QUARANTINE:
            priority = 0
        else:
            priority = 2
        entries.append(LinkGraphBetaFrontierReviewEntry(row.record_id, row.operation, row.observed_state, decision.disposition.value, row.observed_issue_codes, priority, decision.rationale))
    values = tuple(sorted(entries, key=lambda item: (item.priority, item.record_id)))
    return LinkGraphBetaFrontierReviewQueue(values, bool(values) and len(values) == len(evaluation.rows))


__all__ = ["LinkGraphBetaFrontierReviewEntry", "LinkGraphBetaFrontierReviewQueue", "build_link_graph_beta_frontier_review_queue"]
