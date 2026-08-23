"""Deterministic replay checks for D07."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import (
    ChromatinArchitectureFixture,
    addressed,
)
from .chromatin_architecture_operations import evaluate_chromatin_architecture_fixture
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureReplay:
    fixture_id: str
    first_address: str
    second_address: str
    first_receipt_addresses: tuple[str, ...]
    second_receipt_addresses: tuple[str, ...]
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_chromatin_architecture_fixture(
    fixture: ChromatinArchitectureFixture,
) -> ChromatinArchitectureReplay:
    first = evaluate_chromatin_architecture_fixture(fixture)
    second = evaluate_chromatin_architecture_fixture(fixture)
    deterministic = first.content_address == second.content_address and tuple(
        item.content_address for item in first.receipts
    ) == tuple(item.content_address for item in second.receipts)
    body = {
        "fixture_id": fixture.fixture_id,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "deterministic": deterministic,
    }
    return ChromatinArchitectureReplay(
        fixture_id=fixture.fixture_id,
        first_address=first.content_address,
        second_address=second.content_address,
        first_receipt_addresses=tuple(item.content_address for item in first.receipts),
        second_receipt_addresses=tuple(item.content_address for item in second.receipts),
        deterministic=deterministic,
        accepted=deterministic and first.accepted and second.accepted,
        content_address=addressed(body, "chromatin-replay"),
    )


def replay_chromatin_architecture_is_deterministic(fixture: ChromatinArchitectureFixture) -> bool:
    return replay_chromatin_architecture_fixture(fixture).deterministic


__all__ = [
    "ChromatinArchitectureReplay",
    "replay_chromatin_architecture_fixture",
    "replay_chromatin_architecture_is_deterministic",
]
