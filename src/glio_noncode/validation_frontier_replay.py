"""Replay receipts and deterministic comparisons for Domain 13."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_fixture_eval import (
    evaluate_validation_frontier_fixture,
)
from .validation_frontier_public_data import (
    ValidationFrontierFixture,
    default_validation_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class ValidationFrontierReplayReceipt:
    replay_id: str
    fixture_id: str
    evaluation_address: str
    check_count: int
    passed_check_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierReplayComparison:
    left_address: str
    right_address: str
    drift_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"drift_fields": list(self.drift_fields)}


def replay_validation_frontier(fixture: ValidationFrontierFixture | None = None, *, replay_id: str = "validation-frontier-replay") -> ValidationFrontierReplayReceipt:
    fixture = fixture or default_validation_frontier_fixture()
    evaluation = evaluate_validation_frontier_fixture(fixture)
    body = {"replay_id": replay_id, "fixture_id": fixture.fixture_id, "evaluation_address": evaluation.content_address, "check_count": len(evaluation.checks), "passed_check_count": evaluation.passed_checks, "accepted": evaluation.accepted}
    return ValidationFrontierReplayReceipt(**body, content_address=content_hash(body))


def compare_validation_frontier_replays(left: ValidationFrontierReplayReceipt, right: ValidationFrontierReplayReceipt) -> ValidationFrontierReplayComparison:
    drift: list[str] = []
    for field in ("fixture_id", "evaluation_address", "check_count", "passed_check_count", "accepted"):
        if getattr(left, field) != getattr(right, field):
            drift.append(field)
    body = {"left_address": left.content_address, "right_address": right.content_address, "drift_fields": tuple(drift), "accepted": not drift}
    return ValidationFrontierReplayComparison(**body, content_address=content_hash(body))


def validation_frontier_replay_is_deterministic(fixture: ValidationFrontierFixture | None = None) -> bool:
    fixture = fixture or default_validation_frontier_fixture()
    return replay_validation_frontier(fixture, replay_id="one").evaluation_address == replay_validation_frontier(fixture, replay_id="two").evaluation_address


__all__ = ["ValidationFrontierReplayComparison", "ValidationFrontierReplayReceipt", "compare_validation_frontier_replays", "replay_validation_frontier", "validation_frontier_replay_is_deterministic"]
