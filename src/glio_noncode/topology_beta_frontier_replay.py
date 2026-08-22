"""Replay receipts for verifying deterministic fixture evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import evaluate_topology_beta_frontier_fixture
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture, default_topology_beta_frontier_fixture


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierReplayReport:
    fixture_id: str
    expected_address: str
    replay_address: str
    state_match_count: int
    issue_match_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "expected_address": self.expected_address, "replay_address": self.replay_address, "state_match_count": self.state_match_count, "issue_match_count": self.issue_match_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def replay_topology_beta_frontier(fixture: TopologyBetaFrontierFixture | None = None) -> TopologyBetaFrontierReplayReport:
    value = fixture or default_topology_beta_frontier_fixture()
    first = evaluate_topology_beta_frontier_fixture(value)
    second = evaluate_topology_beta_frontier_fixture(value)
    return TopologyBetaFrontierReplayReport(value.fixture_id, first.content_address, second.content_address, second.state_match_count, second.issue_match_count, first.content_address == second.content_address and second.accepted)


__all__ = ["TopologyBetaFrontierReplayReport", "replay_topology_beta_frontier"]
