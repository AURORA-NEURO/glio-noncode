"""Deterministic replay receipts for the C05-C08 fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import (
    evaluate_beta_frontier_fixture,
)
from .workspace_beta_frontier_public_data import BetaFrontierFixture, default_beta_frontier_fixture


@dataclass(frozen=True, slots=True)
class BetaFrontierReplayReceipt:
    """One replay run with source and output addresses."""

    replay_id: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    execution_addresses: tuple[str, ...]
    deterministic: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.replay_id, "replay_id")
        require_non_empty(self.fixture_id, "fixture_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierReplayComparison:
    """Pairwise replay comparison with first difference metadata."""

    replay_id: str
    left_address: str
    right_address: str
    matching: bool
    first_difference: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_beta_frontier(
    fixture: BetaFrontierFixture | None = None,
    *,
    replay_id: str = "workspace-beta-frontier-replay",
) -> BetaFrontierReplayReceipt:
    fixture = fixture or default_beta_frontier_fixture()
    evaluation = evaluate_beta_frontier_fixture(fixture)
    repeat = evaluate_beta_frontier_fixture(fixture)
    addresses = tuple(item.content_address for item in evaluation.executions)
    repeat_addresses = tuple(item.content_address for item in repeat.executions)
    body = {
        "replay_id": replay_id,
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "evaluation_address": evaluation.content_address,
        "execution_addresses": addresses,
        "deterministic": evaluation.content_address == repeat.content_address and addresses == repeat_addresses,
    }
    return BetaFrontierReplayReceipt(**body, content_address=content_hash(body))


def compare_beta_frontier_replays(left: BetaFrontierReplayReceipt, right: BetaFrontierReplayReceipt, *, replay_id: str = "workspace-beta-frontier-compare") -> BetaFrontierReplayComparison:
    matching = left.fixture_address == right.fixture_address and left.evaluation_address == right.evaluation_address and left.execution_addresses == right.execution_addresses
    difference = None
    if left.fixture_address != right.fixture_address:
        difference = "fixture_address"
    elif left.evaluation_address != right.evaluation_address:
        difference = "evaluation_address"
    elif left.execution_addresses != right.execution_addresses:
        difference = "execution_addresses"
    body = {"replay_id": replay_id, "left_address": left.content_address, "right_address": right.content_address, "matching": matching, "first_difference": difference}
    return BetaFrontierReplayComparison(**body, content_address=content_hash(body))


def beta_frontier_replay_is_deterministic(fixture: BetaFrontierFixture | None = None) -> bool:
    receipt = replay_beta_frontier(fixture)
    return receipt.deterministic


__all__ = ["BetaFrontierReplayComparison", "BetaFrontierReplayReceipt", "beta_frontier_replay_is_deterministic", "compare_beta_frontier_replays", "replay_beta_frontier"]
