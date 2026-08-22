"""Deterministic replay receipts for chromatin-alpha execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import (
    evaluate_chromatin_alpha_frontier_fixture,
)
from .chromatin_alpha_frontier_public_data import (
    ChromatinAlphaFrontierFixture,
    default_chromatin_alpha_frontier_fixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReplayReceipt:
    replay_id: str
    fixture_id: str
    evaluation_address: str
    result_addresses: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.replay_id
            or not self.fixture_id
            or not self.evaluation_address
            or not self.result_addresses
        ):
            raise ValidationError("replay receipt is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReplayComparison:
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


def replay_chromatin_alpha_frontier(
    fixture: ChromatinAlphaFrontierFixture | None = None,
    *,
    replay_id: str = "chromatin-alpha-frontier-replay",
) -> ChromatinAlphaFrontierReplayReceipt:
    selected = fixture or default_chromatin_alpha_frontier_fixture()
    evaluation = evaluate_chromatin_alpha_frontier_fixture(selected)
    return ChromatinAlphaFrontierReplayReceipt(
        replay_id,
        selected.fixture_id,
        evaluation.content_address,
        tuple(item.adapter.content_address for item in evaluation.records),
        evaluation.accepted,
    )


def compare_chromatin_alpha_frontier_replays(
    left: ChromatinAlphaFrontierReplayReceipt,
    right: ChromatinAlphaFrontierReplayReceipt,
    *,
    replay_id: str = "chromatin-alpha-frontier-replay-compare",
) -> ChromatinAlphaFrontierReplayComparison:
    matching_evaluation = left.evaluation_address == right.evaluation_address
    matching_results = left.result_addresses == right.result_addresses
    return ChromatinAlphaFrontierReplayComparison(
        replay_id,
        left.content_address,
        right.content_address,
        matching_evaluation,
        matching_results,
        matching_evaluation and matching_results and left.accepted and right.accepted,
    )


def chromatin_alpha_frontier_replay_is_deterministic(
    fixture: ChromatinAlphaFrontierFixture | None = None,
) -> bool:
    left = replay_chromatin_alpha_frontier(fixture, replay_id="chromatin-alpha-replay-a")
    right = replay_chromatin_alpha_frontier(fixture, replay_id="chromatin-alpha-replay-b")
    return compare_chromatin_alpha_frontier_replays(left, right).accepted


__all__ = [
    "ChromatinAlphaFrontierReplayComparison",
    "ChromatinAlphaFrontierReplayReceipt",
    "chromatin_alpha_frontier_replay_is_deterministic",
    "compare_chromatin_alpha_frontier_replays",
    "replay_chromatin_alpha_frontier",
]
