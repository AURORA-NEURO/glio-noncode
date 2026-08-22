"""Disposition policy for baseline link outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


class LinkGraphFoundationFrontierDisposition(StrEnum):
    RELEASE = "release"
    REVIEW = "review"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierPolicyRule:
    rule_id: str
    issue_codes: tuple[str, ...]
    disposition: LinkGraphFoundationFrontierDisposition
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierPolicyDecision:
    record_id: str
    disposition: LinkGraphFoundationFrontierDisposition
    matched_rules: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierPolicyReport:
    rules: tuple[LinkGraphFoundationFrontierPolicyRule, ...]
    decisions: tuple[LinkGraphFoundationFrontierPolicyDecision, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def decision_for(self, record_id: str) -> LinkGraphFoundationFrontierPolicyDecision:
        for item in self.decisions:
            if item.record_id == record_id:
                return item
        raise KeyError(record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rules": [item.to_dict() for item in self.rules], "decisions": [item.to_dict() for item in self.decisions], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_foundation_frontier_policy_rules() -> tuple[LinkGraphFoundationFrontierPolicyRule, ...]:
    return (LinkGraphFoundationFrontierPolicyRule("context", ("context_mismatch",), LinkGraphFoundationFrontierDisposition.ABSTAIN, "foreign context stays outside the requested slice"), LinkGraphFoundationFrontierPolicyRule("absence", ("no_overlap", "no_ccre", "distance_window"), LinkGraphFoundationFrontierDisposition.REVIEW, "absence and baseline windows are not negative mechanism evidence"), LinkGraphFoundationFrontierPolicyRule("ambiguity", ("multiple_overlaps", "distance_tie", "multiple_ccres"), LinkGraphFoundationFrontierDisposition.REVIEW, "all candidate identities remain visible"), LinkGraphFoundationFrontierPolicyRule("evidence", ("single_method", "contradictory_evidence"), LinkGraphFoundationFrontierDisposition.REVIEW, "method paths are not collapsed"))


def evaluate_link_graph_foundation_frontier_policy(evaluation: LinkGraphFoundationFrontierEvaluation, rules: tuple[LinkGraphFoundationFrontierPolicyRule, ...] | None = None) -> LinkGraphFoundationFrontierPolicyReport:
    selected = rules or default_link_graph_foundation_frontier_policy_rules()
    decisions = []
    for row in evaluation.rows:
        matches = tuple(rule.rule_id for rule in selected if set(rule.issue_codes) & set(row.observed_issue_codes))
        disposition = LinkGraphFoundationFrontierDisposition.ABSTAIN if "context" in matches else LinkGraphFoundationFrontierDisposition.REVIEW if matches or row.observed_state in {"ambiguous", "abstained", "absent"} else LinkGraphFoundationFrontierDisposition.RELEASE
        decisions.append(LinkGraphFoundationFrontierPolicyDecision(row.record_id, disposition, matches, ";".join(matches) or "clean bounded baseline"))
    checks = (check("rules", bool(selected), "policy rules exist"), check("decisions", len(decisions) == len(evaluation.rows), "all rows receive decisions"), check("foreign_abstain", all(item.disposition is not LinkGraphFoundationFrontierDisposition.RELEASE for item in decisions if item.record_id.endswith("C3")), "foreign controls abstain"))
    return LinkGraphFoundationFrontierPolicyReport(tuple(selected), tuple(decisions), checks, all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierDisposition", "LinkGraphFoundationFrontierPolicyDecision", "LinkGraphFoundationFrontierPolicyReport", "LinkGraphFoundationFrontierPolicyRule", "default_link_graph_foundation_frontier_policy_rules", "evaluate_link_graph_foundation_frontier_policy"]
