"""Review action plans generated from bounded issue codes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReviewAction:
    action_id: str
    record_id: str
    action_kind: str
    priority: int
    owner_scope: str
    evidence_needed: tuple[str, ...]
    completion_rule: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReviewActionPlan:
    actions: tuple[LinkGraphAlphaFrontierReviewAction, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> tuple[LinkGraphAlphaFrontierReviewAction, ...]:
        return tuple(item for item in self.actions if item.record_id == record_id)

    def by_priority(self, priority: int) -> tuple[LinkGraphAlphaFrontierReviewAction, ...]:
        return tuple(item for item in self.actions if item.priority == priority)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"actions": [item.to_dict() for item in self.actions], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_review_actions(evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierReviewActionPlan:
    actions: list[LinkGraphAlphaFrontierReviewAction] = []
    for row in evaluation.rows:
        for issue in row.observed_issue_codes:
            if issue == "context_mismatch":
                kind, priority, owner, evidence, rule = "context_gate", 0, "context review", ("matching context", "transport justification"), "retain out_of_domain until context matches"
            elif issue in {"direction_disagreement", "contradictory_evidence"}:
                kind, priority, owner, evidence, rule = "contradiction_review", 1, "scientific review", ("source-level direction", "method-specific result"), "reconcile or retain contradiction"
            elif issue in {"missing_components", "tethering_ambiguity", "alternative_gene"}:
                kind, priority, owner, evidence, rule = "candidate_review", 1, "link review", ("all candidate paths", "component receipt"), "retain alternatives or abstain"
            else:
                kind, priority, owner, evidence, rule = "signal_review", 2, "assay review", ("replicate or method support",), "do not promote a single weak path"
            actions.append(LinkGraphAlphaFrontierReviewAction(content_hash((row.record_id, issue, kind)), row.record_id, kind, priority, owner, evidence, rule))
    values = tuple(sorted(actions, key=lambda item: (item.priority, item.record_id, item.action_kind)))
    return LinkGraphAlphaFrontierReviewActionPlan(values, bool(values) and all(item.completion_rule for item in values))


__all__ = ["LinkGraphAlphaFrontierReviewAction", "LinkGraphAlphaFrontierReviewActionPlan", "build_link_graph_alpha_frontier_review_actions"]
