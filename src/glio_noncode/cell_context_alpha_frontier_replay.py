"""Deterministic replay receipt for the C09-C12 fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import (
    CellContextAlphaFrontierEvaluation,
    evaluate_cell_context_alpha_frontier_fixture,
)
from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierReplayReceipt:
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


def replay_cell_context_alpha_frontier(
    fixture: CellContextAlphaFrontierFixture,
) -> CellContextAlphaFrontierReplayReceipt:
    evaluation = evaluate_cell_context_alpha_frontier_fixture(fixture)
    return CellContextAlphaFrontierReplayReceipt(
        fixture.fixture_id,
        fixture.content_address,
        content_hash(evaluation.to_dict()),
        evaluation.state_match_count,
        evaluation.issue_match_count,
        evaluation.accepted,
    )


def replay_cell_context_alpha_frontier_evaluation(
    fixture: CellContextAlphaFrontierFixture,
) -> CellContextAlphaFrontierEvaluation:
    return evaluate_cell_context_alpha_frontier_fixture(fixture)


__all__ = [
    "CellContextAlphaFrontierReplayReceipt",
    "replay_cell_context_alpha_frontier",
    "replay_cell_context_alpha_frontier_evaluation",
]
