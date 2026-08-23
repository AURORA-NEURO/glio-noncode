"""Deterministic replay receipts for the cohort foundation frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation, evaluate_cohort_foundation_frontier_fixture
from .cohort_foundation_frontier_public_data import CohortFoundationFixture, default_cohort_foundation_frontier_fixture


@dataclass(frozen=True, slots=True)
class CohortFoundationReplayReceipt:
    replay_id: str
    fixture_id: str
    evaluation_address: str
    record_addresses: tuple[tuple[str, str], ...]
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationReplayComparison:
    left_replay_id: str
    right_replay_id: str
    same_evaluation: bool
    changed_records: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_cohort_foundation_frontier(fixture: CohortFoundationFixture | None = None, *, replay_id: str = "cohort-foundation-frontier-replay") -> CohortFoundationReplayReceipt:
    value = fixture or default_cohort_foundation_frontier_fixture()
    evaluation = evaluate_cohort_foundation_frontier_fixture(value)
    addresses = tuple((item.record_id, item.content_address) for item in evaluation.executions)
    body = {"replay_id": replay_id, "fixture_id": value.fixture_id, "evaluation": evaluation.content_address, "records": addresses}
    return CohortFoundationReplayReceipt(replay_id, value.fixture_id, evaluation.content_address, addresses, evaluation.accepted, content_hash(body))


def compare_cohort_foundation_frontier_replays(left: CohortFoundationReplayReceipt, right: CohortFoundationReplayReceipt) -> CohortFoundationReplayComparison:
    left_map = dict(left.record_addresses)
    right_map = dict(right.record_addresses)
    changed = tuple(sorted(set(left_map) | set(right_map) - {key for key in left_map.keys() & right_map.keys() if left_map[key] == right_map[key]}))
    # Parentheses above are intentionally expanded for readability by the final set operation.
    changed = tuple(sorted(key for key in set(left_map) | set(right_map) if left_map.get(key) != right_map.get(key)))
    body = {"left": left.replay_id, "right": right.replay_id, "changed": changed}
    return CohortFoundationReplayComparison(left.replay_id, right.replay_id, left.evaluation_address == right.evaluation_address, changed, not changed and left.fixture_id == right.fixture_id, content_hash(body))


def replay_cohort_foundation_frontier_is_deterministic(fixture: CohortFoundationFixture | None = None) -> bool:
    left = replay_cohort_foundation_frontier(fixture, replay_id="determinism-left")
    right = replay_cohort_foundation_frontier(fixture, replay_id="determinism-right")
    return compare_cohort_foundation_frontier_replays(left, right).accepted


__all__ = ["CohortFoundationReplayComparison", "CohortFoundationReplayReceipt", "compare_cohort_foundation_frontier_replays", "replay_cohort_foundation_frontier", "replay_cohort_foundation_frontier_is_deterministic"]
