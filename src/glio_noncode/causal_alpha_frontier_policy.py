"""Bounded disposition policy for C09-C12 row states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_alpha_frontier_adapters import CausalAlphaFrontierEvaluationResult
from .causal_alpha_frontier_public_data import CausalAlphaFrontierOperation
from .causal_reasoning import CausalState
from .serialization import content_hash, jsonable


class CausalAlphaFrontierDisposition(StrEnum):
    ALLOW_DESCRIPTIVE = "allow_descriptive"
    REVIEW = "review"
    QUARANTINE = "quarantine"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierDecision:
    record_id: str
    operation: CausalAlphaFrontierOperation
    state: CausalState
    disposition: CausalAlphaFrontierDisposition
    reason: str
    allowed_claims: tuple[str, ...]
    excluded_claims: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "state": self.state, "disposition": self.disposition, "reason": self.reason, "allowed_claims": self.allowed_claims, "excluded_claims": self.excluded_claims}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierPolicy:
    policy_id: str
    version: str
    decisions: tuple[CausalAlphaFrontierDecision, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"policy_id": self.policy_id, "version": self.version, "decisions": [item.to_dict() for item in self.decisions], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value

    def decide(self, evaluation: Any) -> tuple[CausalAlphaFrontierDecision, ...]:
        return tuple(self._decision(item) for item in evaluation.evaluation.results)

    def _decision(self, item: CausalAlphaFrontierEvaluationResult) -> CausalAlphaFrontierDecision:
        if item.observed_state is CausalState.OUT_OF_DOMAIN:
            disposition = CausalAlphaFrontierDisposition.QUARANTINE
            reason = "exact-context mismatch is excluded from interpretation"
            allowed = ("retain for audit",)
        elif item.observed_state in {CausalState.CONTRADICTORY, CausalState.MEASURED_NEGATIVE}:
            disposition = CausalAlphaFrontierDisposition.REVIEW
            reason = "conflicting or negative evidence requires explicit review"
            allowed = ("retain contradiction", "expose measured state")
        elif item.observed_state is CausalState.SUPPORTED:
            disposition = CausalAlphaFrontierDisposition.ALLOW_DESCRIPTIVE
            reason = "supported bounded evidence may be described within exact context"
            allowed = ("descriptive evidence summary", "source sensitivity summary")
        elif item.observed_state is CausalState.PARTIAL:
            disposition = CausalAlphaFrontierDisposition.REVIEW
            reason = "partial evidence cannot cross the release floor without review"
            allowed = ("retain partial evidence",)
        else:
            disposition = CausalAlphaFrontierDisposition.ABSTAIN
            reason = "insufficient evidence for a bounded disposition"
            allowed = ("retain abstention",)
        excluded = ("causal identification", "clinical diagnosis", "treatment recommendation", "prognosis")
        return CausalAlphaFrontierDecision(item.record_id, item.operation, item.observed_state, disposition, reason, allowed, excluded)


def default_causal_alpha_frontier_policy() -> CausalAlphaFrontierPolicy:
    return CausalAlphaFrontierPolicy("causal-alpha-frontier-policy", "2026.08", (), True)


__all__ = ["CausalAlphaFrontierDecision", "CausalAlphaFrontierDisposition", "CausalAlphaFrontierPolicy", "default_causal_alpha_frontier_policy"]
