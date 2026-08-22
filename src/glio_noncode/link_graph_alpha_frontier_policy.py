"""Policy decisions that keep candidate links bounded and reviewable."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


class LinkGraphAlphaFrontierDisposition(StrEnum):
    RELEASE = "release"
    REVIEW = "review"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierPolicyRule:
    rule_id: str
    description: str
    disposition: LinkGraphAlphaFrontierDisposition
    issue_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierPolicyDecision:
    record_id: str
    disposition: LinkGraphAlphaFrontierDisposition
    matched_rules: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierPolicyReport:
    rules: tuple[LinkGraphAlphaFrontierPolicyRule, ...]
    decisions: tuple[LinkGraphAlphaFrontierPolicyDecision, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def decision_for(self, record_id: str) -> LinkGraphAlphaFrontierPolicyDecision:
        for item in self.decisions:
            if item.record_id == record_id:
                return item
        raise KeyError(record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rules": [item.to_dict() for item in self.rules], "decisions": [item.to_dict() for item in self.decisions], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_alpha_frontier_policy_rules() -> tuple[LinkGraphAlphaFrontierPolicyRule, ...]:
    return (
        LinkGraphAlphaFrontierPolicyRule("context-boundary", "Context-mismatched evidence is excluded from the requested slice.", LinkGraphAlphaFrontierDisposition.ABSTAIN, ("context_mismatch",)),
        LinkGraphAlphaFrontierPolicyRule("contradiction-review", "Contradictory direction or graph evidence remains reviewable.", LinkGraphAlphaFrontierDisposition.REVIEW, ("direction_disagreement", "contradictory_evidence")),
        LinkGraphAlphaFrontierPolicyRule("weak-signal-review", "Weak or single-method paths remain visible with a review disposition.", LinkGraphAlphaFrontierDisposition.REVIEW, ("low_support", "weak_contact", "single_method", "single_assay", "single_evidence")),
        LinkGraphAlphaFrontierPolicyRule("positive-release", "A clean candidate path may enter a bounded aggregate release.", LinkGraphAlphaFrontierDisposition.RELEASE, ()),
    )


def evaluate_link_graph_alpha_frontier_policy(evaluation: LinkGraphAlphaFrontierEvaluation, rules: tuple[LinkGraphAlphaFrontierPolicyRule, ...] | None = None) -> LinkGraphAlphaFrontierPolicyReport:
    selected = rules or default_link_graph_alpha_frontier_policy_rules()
    decisions = []
    for row in evaluation.rows:
        matches = tuple(rule.rule_id for rule in selected if set(rule.issue_codes) & set(row.observed_issue_codes))
        if "context-boundary" in matches:
            disposition = LinkGraphAlphaFrontierDisposition.ABSTAIN
        elif "contradiction-review" in matches or "weak-signal-review" in matches or row.observed_state in {"ambiguous", "abstained"}:
            disposition = LinkGraphAlphaFrontierDisposition.REVIEW
        else:
            disposition = LinkGraphAlphaFrontierDisposition.RELEASE
        decisions.append(LinkGraphAlphaFrontierPolicyDecision(row.record_id, disposition, matches or ("positive-release",), " ; ".join(matches) if matches else "clean bounded candidate path"))
    checks = (check("rules_present", bool(selected), "policy has explicit rules"), check("one_decision_per_row", len(decisions) == len(evaluation.rows), "every replay row receives a disposition"), check("context_abstention", all(item.disposition is not LinkGraphAlphaFrontierDisposition.RELEASE for item in decisions if item.record_id.endswith("C3")), "context controls cannot release"))
    return LinkGraphAlphaFrontierPolicyReport(tuple(selected), tuple(decisions), checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierDisposition", "LinkGraphAlphaFrontierPolicyDecision", "LinkGraphAlphaFrontierPolicyReport", "LinkGraphAlphaFrontierPolicyRule", "default_link_graph_alpha_frontier_policy_rules", "evaluate_link_graph_alpha_frontier_policy"]
