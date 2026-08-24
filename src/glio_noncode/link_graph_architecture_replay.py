"""Deterministic D10 evaluation replay."""

from __future__ import annotations

from dataclasses import dataclass

from .link_graph_architecture_contracts import LinkGraphArchitectureFixture, addressed
from .link_graph_architecture_operations import evaluate_link_graph_architecture_fixture


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureReplay:
    fixture_id: str
    first_address: str
    second_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, object]:
        return (
            self.__dict__
            if hasattr(self, "__dict__")
            else {
                "fixture_id": self.fixture_id,
                "first_address": self.first_address,
                "second_address": self.second_address,
                "accepted": self.accepted,
                "content_address": self.content_address,
            }
        )


def replay_link_graph_architecture_fixture(
    fixture: LinkGraphArchitectureFixture,
) -> LinkGraphArchitectureReplay:
    first = evaluate_link_graph_architecture_fixture(fixture)
    second = evaluate_link_graph_architecture_fixture(fixture)
    accepted = (
        first.accepted and second.accepted and first.content_address == second.content_address
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "accepted": accepted,
    }
    return LinkGraphArchitectureReplay(
        fixture.fixture_id,
        first.content_address,
        second.content_address,
        accepted,
        addressed(body, "link-replay"),
    )


__all__ = ["LinkGraphArchitectureReplay", "replay_link_graph_architecture_fixture"]
