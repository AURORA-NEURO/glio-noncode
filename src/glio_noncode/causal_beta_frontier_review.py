"""Review queue for incomplete, contradictory, ambiguous, and foreign rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_policy import CausalBetaFrontierDecision, CausalBetaFrontierPolicy, CausalBetaFrontierPolicyDecision, default_causal_beta_frontier_policy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReviewItem:
    queue_id: str
    record_id: str
    operation: str
    priority: str
    decision: str
    state: str
    issue_codes: tuple[str, ...]
    required_checks: tuple[str, ...]
    disposition: str
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking(self) -> bool:
        return self.disposition in {"quarantine", "abstain"}

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"queue_id": self.queue_id, "record_id": self.record_id, "operation": self.operation, "priority": self.priority, "decision": self.decision, "state": self.state, "issue_codes": self.issue_codes, "required_checks": self.required_checks, "disposition": self.disposition, "rationale": self.rationale, "blocking": self.blocking}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReviewQueue:
    queue_id: str
    items: tuple[CausalBetaFrontierReviewItem, ...]
    retained_count: int
    review_count: int
    blocked_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.items if item.blocking)

    def for_priority(self, priority: str) -> tuple[CausalBetaFrontierReviewItem, ...]:
        return tuple(item for item in self.items if item.priority == priority)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"queue_id": self.queue_id, "items": [item.to_dict() for item in self.items], "retained_count": self.retained_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "blocking_record_ids": self.blocking_record_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _priority(decision: CausalBetaFrontierPolicyDecision) -> str:
    if decision.decision is CausalBetaFrontierDecision.QUARANTINE:
        return "critical"
    if decision.decision is CausalBetaFrontierDecision.ABSTAIN:
        return "high"
    if decision.decision is CausalBetaFrontierDecision.REVIEW:
        return "normal"
    return "informational"


def build_causal_beta_frontier_review_queue(evaluation: CausalBetaFrontierEvaluation, policy: CausalBetaFrontierPolicy | None = None, *, queue_id: str = "causal-beta-frontier-review") -> CausalBetaFrontierReviewQueue:
    active = policy or default_causal_beta_frontier_policy()
    decisions = active.decide(evaluation)
    items = tuple(CausalBetaFrontierReviewItem(f"{queue_id}:{item.record_id}", item.record_id, item.operation, _priority(item), item.decision.value, item.state, item.issue_codes, tuple(sorted({f"check:{code}" for code in item.issue_codes})) or ("check:positive-receipt",), item.decision.value, item.reason) for item in decisions)
    retained = sum(item.decision == "retain" for item in items)
    review = sum(item.decision in {"review", "abstain"} for item in items)
    blocked = sum(item.blocking for item in items)
    return CausalBetaFrontierReviewQueue(queue_id, items, retained, review, blocked, bool(items) and len({item.record_id for item in items}) == len(items))


__all__ = ["CausalBetaFrontierReviewItem", "CausalBetaFrontierReviewQueue", "build_causal_beta_frontier_review_queue"]
