"""Conservative publication and review policy for sequence-effect outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_public_data import (
    SequenceEffectFixture,
    SequenceEffectRole,
    SequenceEffectState,
)
from .serialization import content_hash, jsonable


class SequenceEffectDecision(StrEnum):
    ALLOW_RESEARCH = "allow_research"
    WITHHOLD_REVIEW = "withhold_review"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class SequenceEffectPolicyRule:
    rule_id: str
    description: str
    decision: SequenceEffectDecision
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "rule_id": self.rule_id,
                        "description": self.description,
                        "decision": self.decision,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectPolicyDecision:
    record_id: str
    decision: SequenceEffectDecision
    publishable: bool
    rule_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "decision": self.decision,
                        "publishable": self.publishable,
                        "rule_ids": self.rule_ids,
                        "issue_codes": self.issue_codes,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectPolicyReport:
    decisions: tuple[SequenceEffectPolicyDecision, ...]
    rules: tuple[SequenceEffectPolicyRule, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"decisions": self.decisions, "rules": self.rules, "accepted": self.accepted}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "decisions": [item.to_dict() for item in self.decisions],
            "rules": [item.to_dict() for item in self.rules],
            "content_address": self.content_address,
        }


def default_sequence_effect_policy_rules() -> tuple[SequenceEffectPolicyRule, ...]:
    return (
        SequenceEffectPolicyRule(
            "positive-supported",
            "supported positive rows may be shown as research evidence",
            SequenceEffectDecision.ALLOW_RESEARCH,
        ),
        SequenceEffectPolicyRule(
            "positive-partial",
            "partial positive rows require bounded review",
            SequenceEffectDecision.WITHHOLD_REVIEW,
        ),
        SequenceEffectPolicyRule(
            "control-retention",
            "controls remain visible and cannot be promoted",
            SequenceEffectDecision.WITHHOLD_REVIEW,
        ),
        SequenceEffectPolicyRule(
            "abstention",
            "empty or unavailable evidence is abstained",
            SequenceEffectDecision.ABSTAIN,
        ),
        SequenceEffectPolicyRule(
            "no-probability",
            "model deltas are never rendered as probabilities",
            SequenceEffectDecision.WITHHOLD_REVIEW,
        ),
    )


def evaluate_sequence_effect_policy(
    fixture: SequenceEffectFixture, evaluation: SequenceEffectEvaluation
) -> SequenceEffectPolicyReport:
    rules = default_sequence_effect_policy_rules()
    decisions: list[SequenceEffectPolicyDecision] = []
    for execution in evaluation.executions:
        if execution.adapter_state is SequenceEffectState.ABSTAINED:
            decision, publishable, rule_ids = SequenceEffectDecision.ABSTAIN, False, ("abstention",)
        elif (
            execution.role is SequenceEffectRole.POSITIVE
            and execution.adapter_state is SequenceEffectState.SUPPORTED
            and not execution.issue_codes
        ):
            decision, publishable, rule_ids = (
                SequenceEffectDecision.ALLOW_RESEARCH,
                True,
                ("positive-supported", "no-probability"),
            )
        else:
            decision, publishable, rule_ids = (
                SequenceEffectDecision.WITHHOLD_REVIEW,
                False,
                (
                    "control-retention"
                    if execution.role is SequenceEffectRole.CONTROL
                    else "positive-partial",
                    "no-probability",
                ),
            )
        decisions.append(
            SequenceEffectPolicyDecision(
                execution.record_id, decision, publishable, rule_ids, execution.issue_codes
            )
        )
    accepted = (
        len(decisions) == len(fixture.records)
        and all(item.content_address.startswith("sha256:") for item in decisions)
        and not any(
            item.publishable
            and next(
                execution
                for execution in evaluation.executions
                if execution.record_id == item.record_id
            ).role
            is SequenceEffectRole.CONTROL
            for item in decisions
        )
    )
    return SequenceEffectPolicyReport(tuple(decisions), rules, accepted)


__all__ = [
    "SequenceEffectDecision",
    "SequenceEffectPolicyDecision",
    "SequenceEffectPolicyReport",
    "SequenceEffectPolicyRule",
    "default_sequence_effect_policy_rules",
    "evaluate_sequence_effect_policy",
]
