"""Research publication policy for sequence grammar evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    SequenceGrammarRole,
    SequenceGrammarState,
)
from .serialization import content_hash, jsonable


class SequenceGrammarDecision(StrEnum):
    ALLOW_RESEARCH = "allow_research"
    HOLD_REVIEW = "hold_review"
    REJECT_INPUT = "reject_input"


@dataclass(frozen=True, slots=True)
class SequenceGrammarPolicyRule:
    rule_id: str
    title: str
    condition: str
    outcome: SequenceGrammarDecision
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarPolicyDecision:
    record_id: str
    state: SequenceGrammarState
    decision: SequenceGrammarDecision
    publishable: bool
    rule_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.rule_ids:
            raise ValidationError("policy decision requires record and rule IDs")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "state": self.state,
                        "decision": self.decision,
                        "publishable": self.publishable,
                        "rule_ids": self.rule_ids,
                        "reasons": self.reasons,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarPolicyReport:
    accepted: bool
    decisions: tuple[SequenceGrammarPolicyDecision, ...]
    rules: tuple[SequenceGrammarPolicyRule, ...]
    fixture_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.decisions or not self.rules:
            raise ValidationError("policy report requires decisions and rules")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "decisions": self.decisions,
                        "rules": self.rules,
                        "fixture_id": self.fixture_id,
                    }
                ),
            )

    @property
    def publishable_records(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.decisions if item.publishable)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "publishable_records": list(self.publishable_records),
            "decisions": [item.to_dict() for item in self.decisions],
            "rules": [rule.to_dict() for rule in self.rules],
            "content_address": self.content_address,
        }


def default_sequence_grammar_policy_rules() -> tuple[SequenceGrammarPolicyRule, ...]:
    return (
        SequenceGrammarPolicyRule(
            "P01",
            "positive-supported",
            "positive supported result",
            SequenceGrammarDecision.ALLOW_RESEARCH,
            "research-only descriptive output is allowed",
        ),
        SequenceGrammarPolicyRule(
            "P02",
            "control-hold",
            "control record",
            SequenceGrammarDecision.HOLD_REVIEW,
            "controls remain visible but never publishable",
        ),
        SequenceGrammarPolicyRule(
            "P03",
            "review-hold",
            "partial, ambiguous, or abstained result",
            SequenceGrammarDecision.HOLD_REVIEW,
            "missing support requires review",
        ),
        SequenceGrammarPolicyRule(
            "P04",
            "invalid-reject",
            "invalid input",
            SequenceGrammarDecision.REJECT_INPUT,
            "invalid records cannot enter a release",
        ),
        SequenceGrammarPolicyRule(
            "P05",
            "no-clinical-promotion",
            "all outputs",
            SequenceGrammarDecision.HOLD_REVIEW,
            "motif and grammar outputs are not clinical claims",
        ),
    )


def evaluate_sequence_grammar_policy(
    fixture: SequenceGrammarFixture, evaluation: SequenceGrammarEvaluation
) -> SequenceGrammarPolicyReport:
    rules = default_sequence_grammar_policy_rules()
    decisions: list[SequenceGrammarPolicyDecision] = []
    for execution in evaluation.executions:
        if execution.adapter_state is SequenceGrammarState.INVALID:
            decision = SequenceGrammarDecision.REJECT_INPUT
            rule_ids = ("P04", "P05")
            reasons = ("invalid input is retained outside release", "output remains descriptive")
        elif execution.role is SequenceGrammarRole.CONTROL:
            decision = SequenceGrammarDecision.HOLD_REVIEW
            rule_ids = ("P02", "P05")
            reasons = ("control evidence is review-only", "output remains descriptive")
        elif execution.adapter_state is SequenceGrammarState.SUPPORTED:
            decision = SequenceGrammarDecision.ALLOW_RESEARCH
            rule_ids = ("P01", "P05")
            reasons = (
                "positive supported mechanics may be used in research views",
                "output remains descriptive",
            )
        else:
            decision = SequenceGrammarDecision.HOLD_REVIEW
            rule_ids = ("P03", "P05")
            reasons = ("support boundary is incomplete", "output remains descriptive")
        decisions.append(
            SequenceGrammarPolicyDecision(
                execution.record_id,
                execution.adapter_state,
                decision,
                decision is SequenceGrammarDecision.ALLOW_RESEARCH
                and execution.role is SequenceGrammarRole.POSITIVE,
                rule_ids,
                reasons,
            )
        )
    accepted = len(decisions) == len(evaluation.executions) and not any(
        item.publishable and item.decision is not SequenceGrammarDecision.ALLOW_RESEARCH
        for item in decisions
    )
    return SequenceGrammarPolicyReport(accepted, tuple(decisions), rules, fixture.fixture_id)


__all__ = [
    "SequenceGrammarDecision",
    "SequenceGrammarPolicyDecision",
    "SequenceGrammarPolicyReport",
    "SequenceGrammarPolicyRule",
    "default_sequence_grammar_policy_rules",
    "evaluate_sequence_grammar_policy",
]
