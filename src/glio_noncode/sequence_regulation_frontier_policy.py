"""Policy decisions that keep sequence observations inside their boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_public_data import SequenceRegulationState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationPolicyDecision:
    record_id: str
    state: SequenceRegulationState
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
class SequenceRegulationPolicyReport:
    decisions: tuple[SequenceRegulationPolicyDecision, ...]
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


def evaluate_sequence_regulation_policy(
    evaluation: SequenceRegulationEvaluation,
) -> SequenceRegulationPolicyReport:
    decisions = []
    for item in evaluation.records:
        if item.observed_state is SequenceRegulationState.SUPPORTED and item.accepted:
            reasons = ("supported sequence observation", "expected path matched")
            release_allowed = True
        elif item.observed_state is SequenceRegulationState.PARTIAL:
            reasons = ("partial sequence evidence", "retain with visible uncertainty")
            release_allowed = False
        elif item.observed_state is SequenceRegulationState.OUT_OF_DOMAIN:
            reasons = ("context boundary mismatch", "exclude from release")
            release_allowed = False
        else:
            reasons = ("boundary or invalid state", "route for review")
            release_allowed = False
        decisions.append(
            SequenceRegulationPolicyDecision(
                item.record_id, item.observed_state, release_allowed, reasons
            )
        )
    values = tuple(decisions)
    return SequenceRegulationPolicyReport(
        values,
        all(bool(item.reasons) for item in values),
        sum(item.release_allowed for item in values),
        sum(not item.release_allowed for item in values),
    )


__all__ = [
    "SequenceRegulationPolicyDecision",
    "SequenceRegulationPolicyReport",
    "evaluate_sequence_regulation_policy",
]
