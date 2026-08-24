"""Deterministic D11 evaluation replay."""

from __future__ import annotations

from dataclasses import dataclass

from .causal_architecture_contracts import CausalArchitectureFixture, addressed
from .causal_architecture_operations import evaluate_causal_architecture_fixture


@dataclass(frozen=True, slots=True)
class CausalArchitectureReplay:
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


def replay_causal_architecture_fixture(
    fixture: CausalArchitectureFixture,
) -> CausalArchitectureReplay:
    first = evaluate_causal_architecture_fixture(fixture)
    second = evaluate_causal_architecture_fixture(fixture)
    accepted = (
        first.accepted and second.accepted and first.content_address == second.content_address
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "accepted": accepted,
    }
    return CausalArchitectureReplay(
        fixture.fixture_id,
        first.content_address,
        second.content_address,
        accepted,
        addressed(body, "causal-replay"),
    )


__all__ = ["CausalArchitectureReplay", "replay_causal_architecture_fixture"]
