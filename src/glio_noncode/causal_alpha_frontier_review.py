"""Human-review queue projection for partial, contradictory, and foreign rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_policy import CausalAlphaFrontierDecision, CausalAlphaFrontierDisposition
from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierReviewItem:
    review_id: str
    record_id: str
    operation: str
    priority: str
    disposition: CausalAlphaFrontierDisposition
    state: str
    reason: str
    required_evidence: tuple[str, ...]
    source_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"review_id": self.review_id, "record_id": self.record_id, "operation": self.operation, "priority": self.priority, "disposition": self.disposition, "state": self.state, "reason": self.reason, "required_evidence": self.required_evidence, "source_ids": self.source_ids}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierReviewQueue:
    fixture_id: str
    items: tuple[CausalAlphaFrontierReviewItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking_items(self) -> tuple[CausalAlphaFrontierReviewItem, ...]:
        return tuple(item for item in self.items if item.priority == "blocking")

    def for_record(self, record_id: str) -> CausalAlphaFrontierReviewItem:
        return next(item for item in self.items if item.record_id == record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "items": [item.to_dict() for item in self.items], "blocking_items": [item.review_id for item in self.blocking_items], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _priority(decision: CausalAlphaFrontierDecision) -> str:
    if decision.disposition is CausalAlphaFrontierDisposition.QUARANTINE:
        return "blocking"
    if decision.disposition is CausalAlphaFrontierDisposition.REVIEW:
        return "high"
    return "informational"


def _required(decision: CausalAlphaFrontierDecision) -> tuple[str, ...]:
    if decision.disposition is CausalAlphaFrontierDisposition.QUARANTINE:
        return ("reconcile exact context", "do not interpret foreign row")
    if decision.state.value == "contradictory":
        return ("review positive and negative paths", "retain both source receipts")
    if decision.state.value == "measured_negative":
        return ("review assay coverage", "do not convert negative to absence")
    if decision.state.value == "partial":
        return ("supply missing independent evidence", "retain current limitation")
    return ("confirm descriptive claim boundary",)


def build_causal_alpha_frontier_review_queue(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, decisions: tuple[CausalAlphaFrontierDecision, ...]) -> CausalAlphaFrontierReviewQueue:
    records = fixture.record_map()
    items: list[CausalAlphaFrontierReviewItem] = []
    for decision in decisions:
        if decision.disposition is CausalAlphaFrontierDisposition.ALLOW_DESCRIPTIVE:
            continue
        record = records[decision.record_id]
        items.append(CausalAlphaFrontierReviewItem(f"review:{decision.record_id}", decision.record_id, decision.operation.value, _priority(decision), decision.disposition, decision.state.value, decision.reason, _required(decision), record.source_ids))
    accepted = bool(evaluation.accepted and len({item.record_id for item in items}) == len(items) and all(item.required_evidence for item in items))
    return CausalAlphaFrontierReviewQueue(fixture.fixture_id, tuple(items), accepted)


__all__ = ["CausalAlphaFrontierReviewItem", "CausalAlphaFrontierReviewQueue", "build_causal_alpha_frontier_review_queue"]
