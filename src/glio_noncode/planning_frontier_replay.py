"""Replay receipts for deterministic planning runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningFixture, PlanningEvaluation
from .planning_frontier_fixture_eval import evaluate_planning_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningReplayReceipt:
    replay_id: str
    first_address: str
    second_address: str
    identical: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_planning(fixture: PlanningFixture, *, replay_id: str = "planning-replay") -> PlanningReplayReceipt:
    first = evaluate_planning_fixture(fixture)
    second = evaluate_planning_fixture(fixture)
    identical = first.content_address == second.content_address and tuple(item.content_address for item in first.executions) == tuple(item.content_address for item in second.executions)
    body = {"replay_id": replay_id, "first_address": first.content_address, "second_address": second.content_address, "identical": identical, "accepted": identical}
    return PlanningReplayReceipt(**body, content_address=content_hash(body, prefix="planning-replay"))


__all__ = ["PlanningReplayReceipt", "replay_planning"]
