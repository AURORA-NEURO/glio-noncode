"""Deterministic replay receipts for Domain 12 cohort convergence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_fixture_eval import evaluate_cohort_frontier_fixture
from .cohort_frontier_public_data import CohortFrontierFixture, default_cohort_frontier_fixture
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierReplayReceipt:
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
        if self.check_count < self.passed_check_count:
            raise ValueError("passed checks cannot exceed checks")

    @property
    def pass_rate(self) -> float:
        return round(self.passed_check_count / self.check_count, 6) if self.check_count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"pass_rate": self.pass_rate}


@dataclass(frozen=True, slots=True)
class CohortFrontierReplayComparison:
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


def replay_cohort_frontier(fixture: CohortFrontierFixture | None = None, *, replay_id: str = "cohort-frontier-replay") -> CohortFrontierReplayReceipt:
    fixture = fixture or default_cohort_frontier_fixture()
    evaluation = evaluate_cohort_frontier_fixture(fixture)
    body = {"replay_id": replay_id, "fixture_id": fixture.fixture_id, "fixture_address": fixture.content_address, "evaluation_address": evaluation.content_address, "execution_addresses": tuple(item.content_address for item in evaluation.executions), "check_count": len(evaluation.checks), "passed_check_count": evaluation.passed_checks, "accepted": evaluation.accepted}
    return CohortFrontierReplayReceipt(**body, content_address=content_hash(body))


def compare_cohort_frontier_replays(left: CohortFrontierReplayReceipt, right: CohortFrontierReplayReceipt) -> CohortFrontierReplayComparison:
    fields = {"fixture_address": left.fixture_address == right.fixture_address, "evaluation_address": left.evaluation_address == right.evaluation_address, "execution_addresses": left.execution_addresses == right.execution_addresses, "check_outcomes": (left.check_count, left.passed_check_count, left.accepted) == (right.check_count, right.passed_check_count, right.accepted)}
    body = {"left_replay_id": left.replay_id, "right_replay_id": right.replay_id, "same_fixture": fields["fixture_address"], "same_evaluation": fields["evaluation_address"], "same_execution_addresses": fields["execution_addresses"], "same_check_outcomes": fields["check_outcomes"], "drift_fields": tuple(key for key, value in fields.items() if not value), "accepted": all(fields.values())}
    return CohortFrontierReplayComparison(**body, content_address=content_hash(body))


def replay_cohort_frontier_is_deterministic(fixture: CohortFrontierFixture | None = None) -> bool:
    return compare_cohort_frontier_replays(replay_cohort_frontier(fixture, replay_id="left"), replay_cohort_frontier(fixture, replay_id="right")).accepted


__all__ = ["CohortFrontierReplayComparison", "CohortFrontierReplayReceipt", "compare_cohort_frontier_replays", "replay_cohort_frontier", "replay_cohort_frontier_is_deterministic"]
