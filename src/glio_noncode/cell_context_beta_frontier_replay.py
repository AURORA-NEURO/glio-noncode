"""Replay receipt for deterministic beta fixture evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import (
    CellContextBetaFrontierEvaluation,
    evaluate_cell_context_beta_frontier_fixture,
)
from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierReplayReceipt:
    fixture_id: str
    fixture_address: str
    replay_address: str
    state_match_count: int
    issue_match_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_cell_context_beta_frontier(
    fixture: CellContextBetaFrontierFixture,
) -> CellContextBetaFrontierReplayReceipt:
    evaluation = evaluate_cell_context_beta_frontier_fixture(fixture)
    replay_address = content_hash(evaluation.to_dict())
    return CellContextBetaFrontierReplayReceipt(
        fixture.fixture_id,
        fixture.content_address,
        replay_address,
        evaluation.state_match_count,
        evaluation.issue_match_count,
        evaluation.accepted,
    )


def replay_cell_context_beta_frontier_evaluation(
    fixture: CellContextBetaFrontierFixture,
) -> CellContextBetaFrontierEvaluation:
    return evaluate_cell_context_beta_frontier_fixture(fixture)


__all__ = [
    "CellContextBetaFrontierReplayReceipt",
    "replay_cell_context_beta_frontier",
    "replay_cell_context_beta_frontier_evaluation",
]
