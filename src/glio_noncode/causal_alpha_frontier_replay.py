"""Deterministic replay receipt for the closed public fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_fixture_eval import evaluate_causal_alpha_frontier_fixture_deep
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierReplayReceipt:
    replay_id: str
    fixture_id: str
    first_address: str
    second_address: str
    result_addresses: tuple[str, ...]
    deterministic: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"replay_id": self.replay_id, "fixture_id": self.fixture_id, "first_address": self.first_address, "second_address": self.second_address, "result_addresses": self.result_addresses, "deterministic": self.deterministic, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def replay_causal_alpha_frontier(fixture: CausalAlphaFrontierFixture, *, replay_id: str = "causal-alpha-frontier-replay") -> CausalAlphaFrontierReplayReceipt:
    first = evaluate_causal_alpha_frontier_fixture_deep(fixture)
    second = evaluate_causal_alpha_frontier_fixture_deep(fixture)
    first_rows = tuple(item.content_address for item in first.evaluation.results)
    second_rows = tuple(item.content_address for item in second.evaluation.results)
    return CausalAlphaFrontierReplayReceipt(replay_id, fixture.fixture_id, first.content_address, second.content_address, first_rows, first.content_address == second.content_address and first_rows == second_rows, first.accepted and second.accepted)


__all__ = ["CausalAlphaFrontierReplayReceipt", "replay_causal_alpha_frontier"]
