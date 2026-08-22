"""Disposition policy for positive and control beta-link outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierRole
from .serialization import content_hash, jsonable


class LinkGraphBetaFrontierDisposition(StrEnum):
    RETAIN = "retain"
    REVIEW = "review"
    ABSTAIN = "abstain"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierPolicyDecision:
    record_id: str
    role: str
    state: str
    disposition: LinkGraphBetaFrontierDisposition
    issue_codes: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierPolicyReport:
    decisions: tuple[LinkGraphBetaFrontierPolicyDecision, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_disposition(self, disposition: LinkGraphBetaFrontierDisposition | str) -> tuple[LinkGraphBetaFrontierPolicyDecision, ...]:
        value = LinkGraphBetaFrontierDisposition(str(disposition))
        return tuple(item for item in self.decisions if item.disposition is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"decisions": [item.to_dict() for item in self.decisions], "disposition_counts": {item.value: len(self.for_disposition(item)) for item in LinkGraphBetaFrontierDisposition}, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_beta_frontier_policy(evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierPolicyReport:
    decisions = []
    for row in evaluation.rows:
        if row.observed_state == "out_of_domain":
            disposition, rationale = LinkGraphBetaFrontierDisposition.QUARANTINE, "foreign context is not transported"
        elif row.observed_state in {"abstained", "contradictory"}:
            disposition, rationale = LinkGraphBetaFrontierDisposition.ABSTAIN, "missing or conflicting evidence remains visible"
        elif row.role == LinkGraphBetaFrontierRole.POSITIVE.value:
            disposition, rationale = LinkGraphBetaFrontierDisposition.RETAIN, "positive aggregate baseline is retained with limitations"
        else:
            disposition, rationale = LinkGraphBetaFrontierDisposition.REVIEW, "control outcome is retained for review"
        decisions.append(LinkGraphBetaFrontierPolicyDecision(row.record_id, row.role, row.observed_state, disposition, row.observed_issue_codes, rationale))
    values = tuple(decisions)
    return LinkGraphBetaFrontierPolicyReport(values, bool(values) and all(item.disposition for item in values))


__all__ = ["LinkGraphBetaFrontierDisposition", "LinkGraphBetaFrontierPolicyDecision", "LinkGraphBetaFrontierPolicyReport", "evaluate_link_graph_beta_frontier_policy"]
