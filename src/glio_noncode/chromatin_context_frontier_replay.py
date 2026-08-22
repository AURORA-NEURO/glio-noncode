"""Deterministic replay receipts for the closed context fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import evaluate_chromatin_context_frontier_fixture
from .chromatin_context_frontier_public_data import ChromatinContextFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierReplayReceipt:
    replay_id: str
    fixture_address: str
    first_result_address: str
    second_result_address: str
    deterministic: bool
    accepted: bool
    checked_record_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.replay_id
            or not self.fixture_address
            or not self.first_result_address
            or not self.second_result_address
        ):
            raise ValidationError("replay receipt is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_chromatin_context_frontier(
    fixture: ChromatinContextFrontierFixture,
    *,
    replay_id: str = "chromatin-context-frontier-replay",
) -> ChromatinContextFrontierReplayReceipt:
    first = evaluate_chromatin_context_frontier_fixture(fixture)
    second = evaluate_chromatin_context_frontier_fixture(fixture)
    first_address = content_hash(first.to_dict())
    second_address = content_hash(second.to_dict())
    deterministic = first_address == second_address
    return ChromatinContextFrontierReplayReceipt(
        replay_id,
        fixture.content_address,
        first_address,
        second_address,
        deterministic,
        deterministic and first.accepted and second.accepted,
        len(fixture.records),
    )


__all__ = [
    "ChromatinContextFrontierReplayReceipt",
    "replay_chromatin_context_frontier",
]
