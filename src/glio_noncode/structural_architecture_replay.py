"""Deterministic replay checks for D02 architecture fixtures and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .structural_architecture_contracts import StructuralArchitectureFixture, addressed
from .structural_architecture_operations import evaluate_structural_architecture_fixture
from .structural_architecture_public_data import default_structural_architecture_fixture


@dataclass(frozen=True, slots=True)
class StructuralArchitectureReplayReceipt:
    fixture_id: str
    run_count: int
    first_address: str
    second_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "run_count": self.run_count,
            "first_address": self.first_address,
            "second_address": self.second_address,
            "deterministic": self.deterministic,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def replay_structural_architecture(
    fixture: StructuralArchitectureFixture | str | Path | None = None,
) -> StructuralArchitectureReplayReceipt:
    """Execute the same fixture twice and compare complete evaluation addresses."""

    value = (
        fixture
        if isinstance(fixture, StructuralArchitectureFixture)
        else default_structural_architecture_fixture(fixture)
        if fixture is not None
        else default_structural_architecture_fixture()
    )
    first = evaluate_structural_architecture_fixture(value)
    second = evaluate_structural_architecture_fixture(value)
    deterministic = (
        first.content_address == second.content_address and first.to_dict() == second.to_dict()
    )
    body = {
        "fixture_id": value.fixture_id,
        "run_count": 2,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "deterministic": deterministic,
        "accepted": first.accepted and second.accepted,
    }
    return StructuralArchitectureReplayReceipt(
        **body, content_address=addressed(body, "structural-replay")
    )


def replay_is_deterministic(receipt: StructuralArchitectureReplayReceipt) -> bool:
    return (
        receipt.accepted
        and receipt.deterministic
        and receipt.first_address == receipt.second_address
    )


__all__ = [
    "StructuralArchitectureReplayReceipt",
    "replay_is_deterministic",
    "replay_structural_architecture",
]
