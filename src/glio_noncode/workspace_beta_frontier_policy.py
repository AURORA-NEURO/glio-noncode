"""Research-use policy decisions for projection outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation, BetaFrontierExecution
from .workspace_beta_frontier_public_data import BetaFrontierOperation


class BetaFrontierDecision(StrEnum):
    """Disposition used by quality, review, and release layers."""

    READY = "ready"
    HOLD = "hold"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class BetaFrontierPolicyRule:
    """Named rule with stable priority and rationale."""

    rule_id: str
    priority: int
    operation: BetaFrontierOperation | None
    required_state: tuple[str, ...]
    decision: BetaFrontierDecision
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.rule_id, "rule_id")
        require_non_empty(self.rationale, "rationale")
        if self.priority < 1:
            raise ValueError("beta frontier policy priority must be positive")

    def matches(self, execution: BetaFrontierExecution) -> bool:
        return (self.operation is None or execution.operation is self.operation) and execution.state in self.required_state

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierPolicyDecision:
    """Decision for one executed projection row."""

    record_id: str
    operation: BetaFrontierOperation
    decision: BetaFrontierDecision
    rule_id: str
    state: str
    issue_codes: tuple[str, ...]
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierPolicy:
    """Ordered policy set applied without changing projection results."""

    policy_id: str
    version: str
    rules: tuple[BetaFrontierPolicyRule, ...]
    boundary: str
    content_address: str

    def decide_one(self, execution: BetaFrontierExecution) -> BetaFrontierPolicyDecision:
        rule = next((item for item in sorted(self.rules, key=lambda value: value.priority) if item.matches(execution)), None)
        if rule is None:
            decision = BetaFrontierDecision.ABSTAIN
            rule_id = "default-abstain"
            rationale = "no rule matched the projection state"
        else:
            decision = rule.decision
            rule_id = rule.rule_id
            rationale = rule.rationale
        body = {
            "record_id": execution.record_id,
            "operation": execution.operation,
            "decision": decision,
            "rule_id": rule_id,
            "state": execution.state,
            "issue_codes": execution.issue_codes,
            "rationale": rationale,
        }
        return BetaFrontierPolicyDecision(**body, content_address=content_hash(body))

    def decide(self, evaluation: BetaFrontierEvaluation) -> tuple[BetaFrontierPolicyDecision, ...]:
        return tuple(self.decide_one(item) for item in evaluation.executions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _rule(rule_id: str, priority: int, operation: BetaFrontierOperation | None, states: tuple[str, ...], decision: BetaFrontierDecision, rationale: str) -> BetaFrontierPolicyRule:
    body = {"rule_id": rule_id, "priority": priority, "operation": operation, "required_state": states, "decision": decision, "rationale": rationale}
    return BetaFrontierPolicyRule(**body, content_address=content_hash(body))


def default_beta_frontier_policy() -> BetaFrontierPolicy:
    """Return the policy used by the release rehearsal."""

    rules = (
        _rule("hold-invalid", 1, None, ("invalid",), BetaFrontierDecision.HOLD, "invalid projection input requires review"),
        _rule("hold-context", 2, None, ("out_of_domain", "contradictory"), BetaFrontierDecision.HOLD, "context or contradiction boundary prevents promotion"),
        _rule("hold-partial", 3, None, ("partial", "incomplete"), BetaFrontierDecision.HOLD, "partial or incomplete projection remains review-visible"),
        _rule("hold-absent", 4, None, ("absent", "abstained"), BetaFrontierDecision.ABSTAIN, "missing observations do not become negative evidence"),
        _rule("ready-topology", 10, BetaFrontierOperation.TOPOLOGY_VIEWPORT, ("supported",), BetaFrontierDecision.READY, "supported topology viewport is renderable with receipts"),
        _rule("ready-chain", 11, BetaFrontierOperation.CAUSAL_CHAIN, ("complete",), BetaFrontierDecision.READY, "complete chain remains an evidence summary"),
        _rule("ready-posterior", 12, BetaFrontierOperation.POSTERIOR_DECOMPOSITION, ("supported",), BetaFrontierDecision.READY, "reconciled posterior proxy is renderable with calibration visible"),
        _rule("ready-table", 13, BetaFrontierOperation.EVIDENCE_TABLE, ("supported",), BetaFrontierDecision.READY, "supported table page is renderable with filters retained"),
    )
    body = {"policy_id": "workspace-beta-frontier-policy", "version": "2026.08.d15.c05-c08.v1", "rules": rules, "boundary": "research_use_only"}
    return BetaFrontierPolicy(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierDecision", "BetaFrontierPolicy", "BetaFrontierPolicyDecision", "BetaFrontierPolicyRule", "default_beta_frontier_policy"]
