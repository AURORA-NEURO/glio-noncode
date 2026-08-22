"""Deterministic replay and drift detection for causal frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_fixture_eval import evaluate_causal_frontier_fixture
from .causal_frontier_public_data import CausalFrontierFixture, default_causal_frontier_fixture
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierReplayReceipt:
    replay_id: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    execution_addresses: tuple[str, ...]
    check_count: int
    passed_check_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.replay_id, "replay_id")
        require_non_empty(self.fixture_id, "fixture_id")
        if self.check_count < self.passed_check_count:
            raise ValueError("passed checks cannot exceed checks")

    @property
    def pass_rate(self) -> float:
        return round(self.passed_check_count / self.check_count, 6) if self.check_count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"pass_rate": self.pass_rate}


@dataclass(frozen=True, slots=True)
class CausalFrontierReplayComparison:
    left_replay_id: str
    right_replay_id: str
    same_fixture: bool
    same_evaluation: bool
    same_execution_addresses: bool
    same_check_outcomes: bool
    drift_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_causal_frontier(
    fixture: CausalFrontierFixture | None = None,
    *,
    replay_id: str = "causal-frontier-replay",
) -> CausalFrontierReplayReceipt:
    fixture = fixture or default_causal_frontier_fixture()
    require_non_empty(replay_id, "replay_id")
    evaluation = evaluate_causal_frontier_fixture(fixture)
    body = {
        "replay_id": replay_id,
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "evaluation_address": evaluation.content_address,
        "execution_addresses": tuple(item.content_address for item in evaluation.executions),
        "check_count": len(evaluation.checks),
        "passed_check_count": evaluation.passed_checks,
        "accepted": evaluation.accepted,
    }
    return CausalFrontierReplayReceipt(**body, content_address=content_hash(body))


def compare_causal_frontier_replays(
    left: CausalFrontierReplayReceipt,
    right: CausalFrontierReplayReceipt,
) -> CausalFrontierReplayComparison:
    drift: list[str] = []
    same_fixture = left.fixture_address == right.fixture_address
    same_evaluation = left.evaluation_address == right.evaluation_address
    same_execution = left.execution_addresses == right.execution_addresses
    same_checks = (left.check_count, left.passed_check_count, left.accepted) == (
        right.check_count,
        right.passed_check_count,
        right.accepted,
    )
    if not same_fixture:
        drift.append("fixture_address")
    if not same_evaluation:
        drift.append("evaluation_address")
    if not same_execution:
        drift.append("execution_addresses")
    if not same_checks:
        drift.append("check_outcomes")
    body = {
        "left_replay_id": left.replay_id,
        "right_replay_id": right.replay_id,
        "same_fixture": same_fixture,
        "same_evaluation": same_evaluation,
        "same_execution_addresses": same_execution,
        "same_check_outcomes": same_checks,
        "drift_fields": tuple(drift),
        "accepted": not drift,
    }
    return CausalFrontierReplayComparison(**body, content_address=content_hash(body))


def replay_is_deterministic(fixture: CausalFrontierFixture | None = None) -> bool:
    left = replay_causal_frontier(fixture, replay_id="determinism-left")
    right = replay_causal_frontier(fixture, replay_id="determinism-right")
    return compare_causal_frontier_replays(left, right).accepted


__all__ = [
    "CausalFrontierReplayComparison",
    "CausalFrontierReplayReceipt",
    "compare_causal_frontier_replays",
    "replay_causal_frontier",
    "replay_is_deterministic",
]
