"""Stable review views suitable for human inspection and CSV export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_policy import CausalAlphaFrontierDecision
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .causal_alpha_frontier_reconciliation import CausalAlphaFrontierReconciliation
from .causal_alpha_frontier_review import CausalAlphaFrontierReviewQueue
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierReviewViewRow:
    record_id: str
    operation: str
    role: str
    context_key: str
    expected_state: str
    observed_state: str
    disposition: str
    review_id: str | None
    source_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "role": self.role, "context_key": self.context_key, "expected_state": self.expected_state, "observed_state": self.observed_state, "disposition": self.disposition, "review_id": self.review_id, "source_ids": self.source_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierReviewView:
    fixture_id: str
    rows: tuple[CausalAlphaFrontierReviewViewRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "rows": [item.to_dict() for item in self.rows], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value

    def to_markdown(self) -> str:
        lines = ["| Record | Operation | Expected | Observed | Disposition | Review |", "| --- | --- | --- | --- | --- | --- |"]
        lines.extend(f"| {row.record_id} | {row.operation} | {row.expected_state} | {row.observed_state} | {row.disposition} | {row.review_id or '-'} |" for row in self.rows)
        return "\n".join(lines) + "\n"


def build_causal_alpha_frontier_review_view(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, decisions: tuple[CausalAlphaFrontierDecision, ...], reconciliation: CausalAlphaFrontierReconciliation, review: CausalAlphaFrontierReviewQueue) -> CausalAlphaFrontierReviewView:
    records = fixture.record_map()
    decision_map = {item.record_id: item for item in decisions}
    review_map = {item.record_id: item for item in review.items}
    rows: list[CausalAlphaFrontierReviewViewRow] = []
    for result in evaluation.evaluation.results:
        record = records[result.record_id]
        decision = decision_map[result.record_id]
        review_item = review_map.get(result.record_id)
        rows.append(CausalAlphaFrontierReviewViewRow(result.record_id, result.operation.value, record.role.value, record.context_key, result.expected_state.value, result.observed_state.value, decision.disposition.value, review_item.review_id if review_item else None, record.source_ids, result.accepted))
    accepted = bool(reconciliation.accepted and len(rows) == len(fixture.records) and tuple(item.record_id for item in rows) == tuple(item.record_id for item in fixture.records))
    return CausalAlphaFrontierReviewView(fixture.fixture_id, tuple(rows), accepted)


__all__ = ["CausalAlphaFrontierReviewView", "CausalAlphaFrontierReviewViewRow", "build_causal_alpha_frontier_review_view"]
