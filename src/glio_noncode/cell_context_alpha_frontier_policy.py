"""Interpretation and review policy for descriptive context-alpha outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierPolicyDecision:
    record_id: str
    action: str
    rationale: str
    review_required: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierPolicyReport:
    decisions: tuple[CellContextAlphaFrontierPolicyDecision, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValueError("alpha policy report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def review_count(self) -> int:
        return sum(item.review_required for item in self.decisions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"review_count": self.review_count}


def evaluate_cell_context_alpha_frontier_policy(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierPolicyReport:
    decisions = []
    for row in evaluation.records:
        state = row.observed_state
        if state == "supported":
            action, review, rationale = (
                "retain_descriptive_prior",
                False,
                "support or delta is descriptive and context-qualified",
            )
        elif state == "out_of_domain":
            action, review, rationale = (
                "refuse_context_transport",
                True,
                "foreign context is refused",
            )
        elif state == "ambiguous":
            action, review, rationale = (
                "queue_margin_review",
                True,
                "candidate or territory scores are close",
            )
        elif state == "partial":
            action, review, rationale = (
                "retain_with_issue_review",
                True,
                "malformed or one-sided evidence remains visible",
            )
        else:
            action, review, rationale = (
                "abstain",
                True,
                "no bounded descriptive release is available",
            )
        decisions.append(
            CellContextAlphaFrontierPolicyDecision(row.record_id, action, rationale, review)
        )
    return CellContextAlphaFrontierPolicyReport(tuple(decisions), evaluation.accepted)


__all__ = [
    "CellContextAlphaFrontierPolicyDecision",
    "CellContextAlphaFrontierPolicyReport",
    "evaluate_cell_context_alpha_frontier_policy",
]
