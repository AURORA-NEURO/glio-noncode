"""Sanitized review rows and view projections for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_policy import BetaFrontierPolicyDecision
from .workspace_beta_frontier_public_data import BetaFrontierFixture
from .workspace_beta_frontier_release import BetaFrontierReleaseManifest


@dataclass(frozen=True, slots=True)
class BetaFrontierReviewRow:
    """Review row with only stable IDs, state, and declared rationale."""

    row_id: str
    record_id: str
    operation: str
    role: str
    state: str
    decision: str
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    notes: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierReviewView:
    """Ordered review view used by queue and export layers."""

    fixture_id: str
    rows: tuple[BetaFrontierReviewRow, ...]
    ready_count: int
    held_count: int
    abstain_count: int
    release_state: str
    content_address: str

    def for_operation(self, operation: str) -> tuple[BetaFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_beta_frontier_review_view(
    fixture: BetaFrontierFixture,
    evaluation: BetaFrontierEvaluation,
    decisions: tuple[BetaFrontierPolicyDecision, ...],
    release: BetaFrontierReleaseManifest,
) -> BetaFrontierReviewView:
    """Build a stable row per execution for human review."""

    decision_map = {item.record_id: item for item in decisions}
    records = fixture.record_map()
    rows = tuple(
        BetaFrontierReviewRow(
            row_id=f"review:{execution.record_id}",
            record_id=execution.record_id,
            operation=execution.operation.value,
            role=execution.role.value,
            state=execution.state,
            decision=decision_map[execution.record_id].decision.value,
            issue_codes=execution.issue_codes,
            source_ids=records[execution.record_id].source_ids,
            notes=records[execution.record_id].notes,
            content_address=content_hash((execution.content_address, decision_map[execution.record_id].content_address)),
        )
        for execution in evaluation.executions
    )
    ready = sum(item.decision == "ready" for item in rows)
    held = sum(item.decision == "hold" for item in rows)
    abstain = sum(item.decision == "abstain" for item in rows)
    body = {"fixture_id": fixture.fixture_id, "rows": rows, "ready_count": ready, "held_count": held, "abstain_count": abstain, "release_state": release.state.value}
    return BetaFrontierReviewView(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierReviewRow", "BetaFrontierReviewView", "build_beta_frontier_review_view"]
