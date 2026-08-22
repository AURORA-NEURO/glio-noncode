"""Policy dispositions for methylation release and review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import MethylationFrontierEvaluation
from .methylation_frontier_public_data import MethylationFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierPolicyDecision:
    record_id: str
    state: MethylationFrontierState
    release_allowed: bool
    reasons: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.reasons:
            raise ValidationError("policy decision requires identity and reasons")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierPolicyReport:
    decisions: tuple[MethylationFrontierPolicyDecision, ...]
    accepted: bool
    release_count: int
    review_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValidationError("policy report requires decisions")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_methylation_frontier_policy(
    evaluation: MethylationFrontierEvaluation,
) -> MethylationFrontierPolicyReport:
    decisions = []
    for item in evaluation.records:
        if item.observed_state is MethylationFrontierState.SUPPORTED and item.accepted:
            allowed = True
            reasons = ("supported aggregate observation", "expected path matched")
        elif item.observed_state is MethylationFrontierState.PARTIAL:
            allowed = False
            reasons = ("support is partial", "retain explicit uncertainty and review")
        elif item.observed_state is MethylationFrontierState.OUT_OF_DOMAIN:
            allowed = False
            reasons = ("context or coordinate support is outside boundary", "exclude from release")
        else:
            allowed = False
            reasons = ("invalid, absent, or abstained path", "route to review")
        decisions.append(
            MethylationFrontierPolicyDecision(item.record_id, item.observed_state, allowed, reasons)
        )
    values = tuple(decisions)
    return MethylationFrontierPolicyReport(
        values,
        all(bool(item.reasons) for item in values),
        sum(item.release_allowed for item in values),
        sum(not item.release_allowed for item in values),
    )


__all__ = [
    "MethylationFrontierPolicyDecision",
    "MethylationFrontierPolicyReport",
    "evaluate_methylation_frontier_policy",
]
