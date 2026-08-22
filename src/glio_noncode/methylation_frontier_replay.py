"""Replay receipts for deterministic methylation fixture execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import evaluate_methylation_frontier_fixture
from .methylation_frontier_public_data import (
    MethylationFrontierFixture,
    default_methylation_frontier_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierReplayReceipt:
    replay_id: str
    fixture_id: str
    evaluation_address: str
    result_addresses: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.replay_id or not self.fixture_id or not self.evaluation_address:
            raise ValidationError("replay receipt is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierReplayComparison:
    replay_id: str
    left_address: str
    right_address: str
    matching_evaluation: bool
    matching_results: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.replay_id or not self.left_address or not self.right_address:
            raise ValidationError("replay comparison is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_methylation_frontier(
    fixture: MethylationFrontierFixture | None = None,
    *,
    replay_id: str = "methylation-frontier-replay",
) -> MethylationFrontierReplayReceipt:
    fixture = fixture or default_methylation_frontier_fixture()
    evaluation = evaluate_methylation_frontier_fixture(fixture)
    return MethylationFrontierReplayReceipt(
        replay_id=replay_id,
        fixture_id=fixture.fixture_id,
        evaluation_address=evaluation.content_address,
        result_addresses=tuple(item.adapter.content_address for item in evaluation.records),
        accepted=evaluation.accepted,
    )


def compare_methylation_frontier_replays(
    left: MethylationFrontierReplayReceipt,
    right: MethylationFrontierReplayReceipt,
    *,
    replay_id: str = "methylation-frontier-replay-compare",
) -> MethylationFrontierReplayComparison:
    matching_evaluation = left.evaluation_address == right.evaluation_address
    matching_results = left.result_addresses == right.result_addresses
    return MethylationFrontierReplayComparison(
        replay_id,
        left.content_address,
        right.content_address,
        matching_evaluation,
        matching_results,
        matching_evaluation and matching_results and left.accepted and right.accepted,
    )


def methylation_frontier_replay_is_deterministic(
    fixture: MethylationFrontierFixture | None = None,
) -> bool:
    first = replay_methylation_frontier(fixture, replay_id="methylation-replay-a")
    second = replay_methylation_frontier(fixture, replay_id="methylation-replay-b")
    return compare_methylation_frontier_replays(first, second).accepted


__all__ = [
    "MethylationFrontierReplayComparison",
    "MethylationFrontierReplayReceipt",
    "compare_methylation_frontier_replays",
    "methylation_frontier_replay_is_deterministic",
    "replay_methylation_frontier",
]
