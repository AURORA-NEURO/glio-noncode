"""Explicit policy decisions for review and release routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation, GammaFrontierExecution
from .workspace_gamma_frontier_public_data import GammaFrontierOperation


class GammaFrontierDecision(StrEnum):
    """Routing result for one execution."""

    RELEASE = "release"
    REVIEW = "review"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class GammaFrontierPolicyRule:
    """Ordered rule over operation, state, and issue evidence."""

    rule_id: str
    priority: int
    operation: GammaFrontierOperation | None
    states: tuple[str, ...]
    requires_issue: bool | None
    decision: GammaFrontierDecision
    rationale: str
    content_address: str

    def matches(self, execution: GammaFrontierExecution) -> bool:
        return (
            (self.operation is None or self.operation is execution.operation)
            and (not self.states or execution.state in self.states)
            and (self.requires_issue is None or bool(execution.issue_codes) is self.requires_issue)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierPolicyDecision:
    """Decision and matched rule receipt for one execution."""

    record_id: str
    operation: GammaFrontierOperation
    state: str
    decision: GammaFrontierDecision
    rule_id: str
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierPolicy:
    """Deny-by-default ordered policy."""

    rules: tuple[GammaFrontierPolicyRule, ...]
    default_decision: GammaFrontierDecision
    content_address: str

    def decide_one(self, execution: GammaFrontierExecution) -> GammaFrontierPolicyDecision:
        rule = next((item for item in self.rules if item.matches(execution)), None)
        if rule is None:
            decision, rule_id, rationale = (
                self.default_decision,
                "default-hold",
                "no explicit release rule matched",
            )
        else:
            decision, rule_id, rationale = rule.decision, rule.rule_id, rule.rationale
        body = {
            "record_id": execution.record_id,
            "operation": execution.operation,
            "state": execution.state,
            "decision": decision,
            "rule_id": rule_id,
            "rationale": rationale,
        }
        return GammaFrontierPolicyDecision(
            **body, content_address=content_hash(body, prefix="policy")
        )

    def decide(
        self, evaluation: GammaFrontierEvaluation
    ) -> tuple[GammaFrontierPolicyDecision, ...]:
        return tuple(self.decide_one(item) for item in evaluation.executions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _rule(
    rule_id: str,
    priority: int,
    operation: GammaFrontierOperation | None,
    states: tuple[str, ...],
    requires_issue: bool | None,
    decision: GammaFrontierDecision,
    rationale: str,
) -> GammaFrontierPolicyRule:
    body = {
        "rule_id": rule_id,
        "priority": priority,
        "operation": operation,
        "states": states,
        "requires_issue": requires_issue,
        "decision": decision,
        "rationale": rationale,
    }
    return GammaFrontierPolicyRule(**body, content_address=content_hash(body))


def default_gamma_frontier_policy() -> GammaFrontierPolicy:
    """Return explicit release, review, and hold rules."""

    rules = (
        _rule(
            "hold-out-of-domain",
            1,
            None,
            ("out_of_domain",),
            None,
            GammaFrontierDecision.HOLD,
            "foreign context cannot enter a review release",
        ),
        _rule(
            "hold-blocked",
            2,
            None,
            ("blocked", "denied", "abstained"),
            None,
            GammaFrontierDecision.HOLD,
            "blocked, denied, or abstained results require remediation",
        ),
        _rule(
            "hold-expired",
            3,
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            ("expired",),
            None,
            GammaFrontierDecision.HOLD,
            "expired snapshots cannot be released",
        ),
        _rule(
            "review-with-issues",
            4,
            None,
            (),
            True,
            GammaFrontierDecision.REVIEW,
            "visible issues require human review",
        ),
        _rule(
            "review-ready",
            5,
            None,
            ("ready_for_review", "review_required"),
            None,
            GammaFrontierDecision.REVIEW,
            "ready or network-review results need review",
        ),
        _rule(
            "release-verified",
            6,
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            ("verified",),
            False,
            GammaFrontierDecision.RELEASE,
            "verified snapshot may enter research-use packaging",
        ),
        _rule(
            "release-allowed",
            7,
            GammaFrontierOperation.COLLABORATION_ACCESS,
            ("allowed",),
            False,
            GammaFrontierDecision.RELEASE,
            "explicitly allowed access may be packaged",
        ),
        _rule(
            "release-clean-board",
            8,
            GammaFrontierOperation.EXPERIMENT_BOARD,
            ("ready_for_review",),
            False,
            GammaFrontierDecision.REVIEW,
            "board metadata remains review-only",
        ),
    )
    ordered = tuple(sorted(rules, key=lambda item: item.priority))
    body = {"rules": ordered, "default_decision": GammaFrontierDecision.HOLD}
    return GammaFrontierPolicy(
        rules=ordered,
        default_decision=GammaFrontierDecision.HOLD,
        content_address=content_hash(body),
    )


__all__ = [
    "GammaFrontierDecision",
    "GammaFrontierPolicy",
    "GammaFrontierPolicyDecision",
    "GammaFrontierPolicyRule",
    "default_gamma_frontier_policy",
]
