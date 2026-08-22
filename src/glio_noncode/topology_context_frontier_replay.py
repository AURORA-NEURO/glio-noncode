"""Replay receipts for deterministic topology fixture evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash
from .topology_context_frontier_fixture_eval import (
    TopologyContextFrontierEvaluation,
    evaluate_topology_context_frontier_fixture,
)
from .topology_context_frontier_public_data import (
    TopologyContextFrontierFixture,
    default_topology_context_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierReplayReceipt:
    fixture_id: str
    expected_address: str
    replay_address: str
    record_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "expected_address": self.expected_address,
            "replay_address": self.replay_address,
            "record_count": self.record_count,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def replay_topology_context_frontier(
    fixture: TopologyContextFrontierFixture | None = None,
) -> TopologyContextFrontierReplayReceipt:
    value = fixture or default_topology_context_frontier_fixture()
    first = evaluate_topology_context_frontier_fixture(value)
    second = evaluate_topology_context_frontier_fixture(value)
    return TopologyContextFrontierReplayReceipt(
        value.fixture_id,
        first.content_address,
        second.content_address,
        len(second.rows),
        first.accepted and second.accepted and first.content_address == second.content_address,
    )


def replay_topology_context_frontier_evaluation(
    fixture: TopologyContextFrontierFixture | None = None,
) -> TopologyContextFrontierEvaluation:
    return evaluate_topology_context_frontier_fixture(
        fixture or default_topology_context_frontier_fixture()
    )


__all__ = [
    "TopologyContextFrontierReplayReceipt",
    "replay_topology_context_frontier",
    "replay_topology_context_frontier_evaluation",
]
