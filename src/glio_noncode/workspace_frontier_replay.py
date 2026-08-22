"""Replay receipts and drift comparison for workspace projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_frontier_fixture_eval import (
    evaluate_workspace_frontier_fixture,
)
from .workspace_frontier_public_data import (
    WorkspaceFrontierFixture,
    default_workspace_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReplayReceipt:
    replay_id: str
    fixture_id: str
    evaluation_address: str
    execution_addresses: tuple[str, ...]
    stable: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.replay_id, "replay_id")
        require_non_empty(self.fixture_id, "fixture_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReplayComparison:
    left_replay_id: str
    right_replay_id: str
    accepted: bool
    drift_fields: tuple[str, ...]
    left_evaluation_address: str
    right_evaluation_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_workspace_frontier(fixture: WorkspaceFrontierFixture | None = None, *, replay_id: str = "workspace-frontier-replay") -> WorkspaceFrontierReplayReceipt:
    fixture = fixture or default_workspace_frontier_fixture()
    evaluation = evaluate_workspace_frontier_fixture(fixture)
    body = {
        "replay_id": replay_id,
        "fixture_id": fixture.fixture_id,
        "evaluation_address": evaluation.content_address,
        "execution_addresses": tuple(item.content_address for item in evaluation.executions),
        "stable": evaluation.accepted,
    }
    return WorkspaceFrontierReplayReceipt(**body, content_address=content_hash(body))


def compare_workspace_frontier_replays(left: WorkspaceFrontierReplayReceipt, right: WorkspaceFrontierReplayReceipt) -> WorkspaceFrontierReplayComparison:
    drift: list[str] = []
    for name in ("fixture_id", "evaluation_address", "execution_addresses"):
        if getattr(left, name) != getattr(right, name):
            drift.append(name)
    body = {
        "left_replay_id": left.replay_id,
        "right_replay_id": right.replay_id,
        "accepted": not drift,
        "drift_fields": tuple(drift),
        "left_evaluation_address": left.evaluation_address,
        "right_evaluation_address": right.evaluation_address,
    }
    return WorkspaceFrontierReplayComparison(**body, content_address=content_hash(body))


def workspace_frontier_replay_is_deterministic(fixture: WorkspaceFrontierFixture | None = None) -> bool:
    fixture = fixture or default_workspace_frontier_fixture()
    left = replay_workspace_frontier(fixture, replay_id="workspace-frontier-replay-a")
    right = replay_workspace_frontier(fixture, replay_id="workspace-frontier-replay-b")
    return compare_workspace_frontier_replays(left, right).accepted


__all__ = [
    "WorkspaceFrontierReplayComparison",
    "WorkspaceFrontierReplayReceipt",
    "compare_workspace_frontier_replays",
    "replay_workspace_frontier",
    "workspace_frontier_replay_is_deterministic",
]
