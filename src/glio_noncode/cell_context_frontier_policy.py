"""Release policy for context taxonomy and assembly results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierPolicyDecision:
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
            raise ValidationError("cell policy decision is invalid")
        if not self.reason:
            raise ValidationError("cell policy decision needs a reason")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierPolicyReport:
    decisions: tuple[CellContextFrontierPolicyDecision, ...]
    accepted: bool
    release_count: int
    review_count: int
    refusal_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValidationError("cell policy report is empty")
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


def evaluate_cell_context_frontier_policy(
    evaluation: CellContextFrontierEvaluation,
) -> CellContextFrontierPolicyReport:
    decisions = []
    for row in evaluation.records:
        if row.role == "positive" and row.observed_state == "supported":
            decisions.append(
                CellContextFrontierPolicyDecision(
                    row.record_id,
                    row.role,
                    row.observed_state,
                    "release",
                    "supported positive context path",
                    False,
                    True,
                )
            )
        elif row.observed_state == "out_of_domain":
            decisions.append(
                CellContextFrontierPolicyDecision(
                    row.record_id,
                    row.role,
                    row.observed_state,
                    "refuse",
                    "exact context gate blocks transport",
                    False,
                    False,
                )
            )
        elif row.observed_state in {"ambiguous", "contradictory", "partial", "abstained"}:
            decisions.append(
                CellContextFrontierPolicyDecision(
                    row.record_id,
                    row.role,
                    row.observed_state,
                    "review",
                    "uncertainty or conflict requires review",
                    True,
                    False,
                )
            )
        else:
            decisions.append(
                CellContextFrontierPolicyDecision(
                    row.record_id,
                    row.role,
                    row.observed_state,
                    "refuse",
                    "state is not release eligible",
                    False,
                    False,
                )
            )
    release_count = sum(item.decision == "release" for item in decisions)
    review_count = sum(item.decision == "review" for item in decisions)
    refusal_count = sum(item.decision == "refuse" for item in decisions)
    accepted = (
        len(decisions) == len(evaluation.records)
        and release_count == 4
        and review_count >= 1
        and refusal_count >= 1
    )
    return CellContextFrontierPolicyReport(
        tuple(decisions), accepted, release_count, review_count, refusal_count
    )


__all__ = [
    "CellContextFrontierPolicyDecision",
    "CellContextFrontierPolicyReport",
    "evaluate_cell_context_frontier_policy",
]
