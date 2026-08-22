"""Release, review, and refusal policy for context-qualified chromatin evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierPolicyDecision:
    record_id: str
    role: str
    observed_state: str
    decision: str
    reason: str
    review_required: bool
    release_eligible: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or self.decision not in {"release", "review", "refuse"}:
            raise ValidationError("policy decision is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierPolicyReport:
    decisions: tuple[ChromatinContextFrontierPolicyDecision, ...]
    accepted: bool
    release_count: int
    review_count: int
    refusal_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValidationError("policy report requires decisions")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def release_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.decisions if item.decision == "release")

    @property
    def review_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.decisions if item.decision == "review")

    @property
    def refusal_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.decisions if item.decision == "refuse")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "release_ids": list(self.release_ids),
            "review_ids": list(self.review_ids),
            "refusal_ids": list(self.refusal_ids),
        }


def evaluate_chromatin_context_frontier_policy(
    evaluation: ChromatinContextFrontierEvaluation,
) -> ChromatinContextFrontierPolicyReport:
    decisions: list[ChromatinContextFrontierPolicyDecision] = []
    for row in evaluation.records:
        state = row.observed_state
        if row.role == "positive" and state == "supported":
            decision = ChromatinContextFrontierPolicyDecision(
                row.record_id, row.role, state, "release", "supported positive path", False, True
            )
        elif state == "out_of_domain":
            decision = ChromatinContextFrontierPolicyDecision(
                row.record_id,
                row.role,
                state,
                "refuse",
                "context boundary blocks transport",
                False,
                False,
            )
        elif state in {"ambiguous", "partial", "abstained", "invalid"}:
            decision = ChromatinContextFrontierPolicyDecision(
                row.record_id,
                row.role,
                state,
                "review",
                "uncertainty or missingness requires review",
                True,
                False,
            )
        else:
            decision = ChromatinContextFrontierPolicyDecision(
                row.record_id,
                row.role,
                state,
                "refuse",
                "state is not release eligible",
                False,
                False,
            )
        decisions.append(decision)
    release_count = sum(item.decision == "release" for item in decisions)
    review_count = sum(item.decision == "review" for item in decisions)
    refusal_count = sum(item.decision == "refuse" for item in decisions)
    accepted = (
        len(decisions) == len(evaluation.records)
        and release_count == 4
        and review_count >= 1
        and refusal_count >= 1
        and all(bool(item.reason) for item in decisions)
    )
    return ChromatinContextFrontierPolicyReport(
        tuple(decisions), accepted, release_count, review_count, refusal_count
    )


__all__ = [
    "ChromatinContextFrontierPolicyDecision",
    "ChromatinContextFrontierPolicyReport",
    "evaluate_chromatin_context_frontier_policy",
]
