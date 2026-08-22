"""Replay receipts for deterministic C09-C12 evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_fixture_eval import evaluate_gamma_frontier_fixture
from .workspace_gamma_frontier_public_data import (
    GammaFrontierFixture,
    default_gamma_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class GammaFrontierReplayReceipt:
    """One replay result with row addresses and aggregate address."""

    replay_id: str
    fixture_id: str
    evaluation_address: str
    execution_addresses: tuple[str, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.replay_id, "replay_id")
        require_non_empty(self.fixture_id, "fixture_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierReplayComparison:
    """Comparison of two replay receipts."""

    replay_id: str
    left_address: str
    right_address: str
    matching_evaluation: bool
    matching_executions: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_gamma_frontier(
    fixture: GammaFrontierFixture | None = None,
    *,
    replay_id: str = "workspace-gamma-frontier-replay",
) -> GammaFrontierReplayReceipt:
    """Execute a fixture and expose only deterministic addresses."""

    fixture = fixture or default_gamma_frontier_fixture()
    evaluation = evaluate_gamma_frontier_fixture(fixture)
    body = {
        "replay_id": replay_id,
        "fixture_id": fixture.fixture_id,
        "evaluation_address": evaluation.content_address,
        "execution_addresses": tuple(item.content_address for item in evaluation.executions),
        "accepted": evaluation.accepted,
    }
    return GammaFrontierReplayReceipt(**body, content_address=content_hash(body, prefix="replay"))


def compare_gamma_frontier_replays(
    left: GammaFrontierReplayReceipt,
    right: GammaFrontierReplayReceipt,
    *,
    replay_id: str = "workspace-gamma-frontier-compare",
) -> GammaFrontierReplayComparison:
    """Compare evaluation and per-row addresses, retaining both inputs."""

    body = {
        "replay_id": replay_id,
        "left_address": left.content_address,
        "right_address": right.content_address,
        "matching_evaluation": left.evaluation_address == right.evaluation_address,
        "matching_executions": left.execution_addresses == right.execution_addresses,
        "accepted": left.evaluation_address == right.evaluation_address
        and left.execution_addresses == right.execution_addresses
        and left.accepted
        and right.accepted,
    }
    return GammaFrontierReplayComparison(
        **body, content_address=content_hash(body, prefix="replay-compare")
    )


def gamma_frontier_replay_is_deterministic(fixture: GammaFrontierFixture | None = None) -> bool:
    """Run two evaluations and compare their stable result addresses."""

    first = replay_gamma_frontier(fixture, replay_id="gamma-replay-a")
    second = replay_gamma_frontier(fixture, replay_id="gamma-replay-b")
    return compare_gamma_frontier_replays(first, second).accepted


__all__ = [
    "GammaFrontierReplayComparison",
    "GammaFrontierReplayReceipt",
    "compare_gamma_frontier_replays",
    "gamma_frontier_replay_is_deterministic",
    "replay_gamma_frontier",
]
