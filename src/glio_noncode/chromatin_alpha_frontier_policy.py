"""Release and review dispositions for chromatin-alpha results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierPolicyDecision:
    record_id: str
    state: str
    role: str
    release_allowed: bool
    decision: str
    reasons: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.state or not self.decision or not self.reasons:
            raise ValidationError("policy decision is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierPolicyReport:
    decisions: tuple[ChromatinAlphaFrontierPolicyDecision, ...]
    accepted: bool
    release_count: int
    review_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValidationError("policy report requires decisions")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_record(self, record_id: str) -> ChromatinAlphaFrontierPolicyDecision:
        for decision in self.decisions:
            if decision.record_id == record_id:
                return decision
        raise KeyError(record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_chromatin_alpha_frontier_policy(
    evaluation: ChromatinAlphaFrontierEvaluation,
) -> ChromatinAlphaFrontierPolicyReport:
    decisions: list[ChromatinAlphaFrontierPolicyDecision] = []
    for item in evaluation.records:
        if item.role == "positive" and item.accepted and item.observed_state == "supported":
            allowed, decision, reasons = (
                True,
                "release",
                ("positive aggregate path is supported", "expected state and issue floors match"),
            )
        elif item.observed_state == "out_of_domain":
            allowed, decision, reasons = (
                False,
                "quarantine",
                ("context is outside the declared boundary", "do not borrow foreign context"),
            )
        elif item.observed_state in {"invalid", "ambiguous"}:
            allowed, decision, reasons = (
                False,
                "review",
                ("critical or mixed evidence remains", "retain the row for explicit review"),
            )
        else:
            allowed, decision, reasons = (
                False,
                "review",
                ("control or partial path remains visible", "do not promote a bounded observation"),
            )
        decisions.append(
            ChromatinAlphaFrontierPolicyDecision(
                item.record_id, item.observed_state, item.role, allowed, decision, reasons
            )
        )
    values = tuple(decisions)
    return ChromatinAlphaFrontierPolicyReport(
        values,
        all(decision.reasons for decision in values),
        sum(decision.release_allowed for decision in values),
        sum(not decision.release_allowed for decision in values),
    )


__all__ = [
    "ChromatinAlphaFrontierPolicyDecision",
    "ChromatinAlphaFrontierPolicyReport",
    "evaluate_chromatin_alpha_frontier_policy",
]
