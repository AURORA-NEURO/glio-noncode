"""Deterministic replay and comparison receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation, evaluate_causal_foundation_frontier_fixture
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture, default_causal_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierReplayReceipt:
    replay_id: str
    fixture_id: str
    first_address: str
    second_address: str
    row_count: int
    state_match: bool
    issue_match: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def deterministic(self) -> bool:
        return self.first_address == self.second_address and self.state_match and self.issue_match

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"replay_id": self.replay_id, "fixture_id": self.fixture_id, "first_address": self.first_address, "second_address": self.second_address, "row_count": self.row_count, "state_match": self.state_match, "issue_match": self.issue_match, "deterministic": self.deterministic, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierReplayComparison:
    fixture_id: str
    left_address: str
    right_address: str
    changed_record_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def identical(self) -> bool:
        return self.left_address == self.right_address and not self.changed_record_ids

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "left_address": self.left_address, "right_address": self.right_address, "changed_record_ids": self.changed_record_ids, "identical": self.identical, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def replay_causal_foundation_frontier(fixture: CausalFoundationFrontierFixture | None = None, *, replay_id: str = "causal-foundation-frontier-replay") -> CausalFoundationFrontierReplayReceipt:
    value = fixture or default_causal_foundation_frontier_fixture()
    first = evaluate_causal_foundation_frontier_fixture(value)
    second = evaluate_causal_foundation_frontier_fixture(value)
    return CausalFoundationFrontierReplayReceipt(replay_id, value.fixture_id, first.content_address, second.content_address, len(first.rows), first.state_match_count == second.state_match_count, first.issue_match_count == second.issue_match_count, first.content_address == second.content_address and first.accepted and second.accepted)


def compare_causal_foundation_frontier_replays(left: CausalFoundationFrontierEvaluation, right: CausalFoundationFrontierEvaluation) -> CausalFoundationFrontierReplayComparison:
    left_map = {item.record_id: item for item in left.rows}
    right_map = {item.record_id: item for item in right.rows}
    changed = tuple(sorted(record_id for record_id in set(left_map) | set(right_map) if (left_map.get(record_id).observed_state, left_map.get(record_id).observed_issue_codes) != (right_map.get(record_id).observed_state, right_map.get(record_id).observed_issue_codes)))
    return CausalFoundationFrontierReplayComparison(left.fixture_id, left.content_address, right.content_address, changed, left.fixture_id == right.fixture_id and not changed)


def replay_is_deterministic(fixture: CausalFoundationFrontierFixture | None = None) -> bool:
    return replay_causal_foundation_frontier(fixture).deterministic


__all__ = ["CausalFoundationFrontierReplayComparison", "CausalFoundationFrontierReplayReceipt", "compare_causal_foundation_frontier_replays", "replay_causal_foundation_frontier", "replay_is_deterministic"]
