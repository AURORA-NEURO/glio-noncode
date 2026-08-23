"""Deterministic replay checks for the D08 aggregate."""

from __future__ import annotations

from dataclasses import dataclass

from .cell_state_architecture_contracts import CellStateArchitectureFixture, addressed
from .cell_state_architecture_operations import evaluate_cell_state_architecture_fixture


@dataclass(frozen=True, slots=True)
class CellStateArchitectureReplay:
    fixture_id: str
    first_address: str
    second_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "first_address": self.first_address,
            "second_address": self.second_address,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def replay_cell_state_architecture_fixture(
    fixture: CellStateArchitectureFixture,
) -> CellStateArchitectureReplay:
    first = evaluate_cell_state_architecture_fixture(fixture)
    second = evaluate_cell_state_architecture_fixture(fixture)
    accepted = (
        first.accepted and second.accepted and first.content_address == second.content_address
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "accepted": accepted,
    }
    return CellStateArchitectureReplay(
        fixture.fixture_id,
        first.content_address,
        second.content_address,
        accepted,
        addressed(body, "cell-state-replay"),
    )


def replay_cell_state_architecture_checks(fixture: CellStateArchitectureFixture) -> bool:
    return replay_cell_state_architecture_fixture(fixture).accepted


__all__ = [
    "CellStateArchitectureReplay",
    "replay_cell_state_architecture_checks",
    "replay_cell_state_architecture_fixture",
]
