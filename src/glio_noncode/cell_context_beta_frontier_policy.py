"""Release policy that distinguishes usable priors from review-required rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierPolicyDecision:
    record_id: str
    action: str
    rationale: str
    review_required: bool
    evidence_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.action or not self.rationale:
            raise ValidationError("beta policy decision is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierPolicyReport:
    decisions: tuple[CellContextBetaFrontierPolicyDecision, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValidationError("beta policy report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def review_count(self) -> int:
        return sum(item.review_required for item in self.decisions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"review_count": self.review_count}


def evaluate_cell_context_beta_frontier_policy(
    evaluation: CellContextBetaFrontierEvaluation,
) -> CellContextBetaFrontierPolicyReport:
    decisions: list[CellContextBetaFrontierPolicyDecision] = []
    for row in evaluation.records:
        state = row.observed_state
        if state == "supported":
            action, review, rationale = (
                "retain_research_prior",
                False,
                "exact-context candidate retained with bounded support",
            )
        elif state == "out_of_domain":
            action, review, rationale = (
                "refuse_domain_transport",
                True,
                "explicit context or molecular gate refused transport",
            )
        elif state == "ambiguous":
            action, review, rationale = (
                "queue_candidate_review",
                True,
                "candidate alternatives remain within the ambiguity margin",
            )
        elif state == "partial":
            action, review, rationale = (
                "retain_with_quarantine",
                True,
                "usable rows coexist with quarantined parser input",
            )
        else:
            action, review, rationale = (
                "abstain",
                True,
                "the prior does not support a bounded release",
            )
        decisions.append(
            CellContextBetaFrontierPolicyDecision(
                row.record_id,
                action,
                rationale,
                review,
                tuple(row.adapter.measurements.get("evidence_ids", ())),
            )
        )
    return CellContextBetaFrontierPolicyReport(tuple(decisions), evaluation.accepted)


__all__ = [
    "CellContextBetaFrontierPolicyDecision",
    "CellContextBetaFrontierPolicyReport",
    "evaluate_cell_context_beta_frontier_policy",
]
