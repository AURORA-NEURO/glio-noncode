"""Replay receipts and drift comparisons for Domain 14 evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import (
    evaluate_evidence_lifecycle_fixture,
)
from .evidence_lifecycle_frontier_public_data import (
    EvidenceLifecycleFixture,
    default_evidence_lifecycle_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReplayReceipt:
    replay_id: str
    fixture_id: str
    evaluation_address: str
    execution_addresses: tuple[str, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.replay_id, "replay_id")
        require_non_empty(self.evaluation_address, "evaluation_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReplayComparison:
    left_replay_id: str
    right_replay_id: str
    accepted: bool
    drift_fields: tuple[str, ...]
    left_address: str
    right_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_evidence_lifecycle(fixture: EvidenceLifecycleFixture | None = None, *, replay_id: str = "evidence-lifecycle-replay") -> EvidenceLifecycleReplayReceipt:
    fixture = fixture or default_evidence_lifecycle_fixture()
    evaluation = evaluate_evidence_lifecycle_fixture(fixture)
    body = {"replay_id": replay_id, "fixture_id": fixture.fixture_id, "evaluation_address": evaluation.content_address, "execution_addresses": tuple(item.content_address for item in evaluation.executions), "accepted": evaluation.accepted}
    return EvidenceLifecycleReplayReceipt(**body, content_address=content_hash(body))


def compare_evidence_lifecycle_replays(left: EvidenceLifecycleReplayReceipt, right: EvidenceLifecycleReplayReceipt) -> EvidenceLifecycleReplayComparison:
    drift: list[str] = []
    for field in ("fixture_id", "evaluation_address", "execution_addresses", "accepted"):
        if getattr(left, field) != getattr(right, field):
            drift.append(field)
    body = {"left_replay_id": left.replay_id, "right_replay_id": right.replay_id, "accepted": not drift, "drift_fields": tuple(drift), "left_address": left.content_address, "right_address": right.content_address}
    return EvidenceLifecycleReplayComparison(**body, content_address=content_hash(body))


def evidence_lifecycle_replay_is_deterministic(fixture: EvidenceLifecycleFixture | None = None) -> bool:
    fixture = fixture or default_evidence_lifecycle_fixture()
    left = replay_evidence_lifecycle(fixture, replay_id="left")
    right = replay_evidence_lifecycle(fixture, replay_id="right")
    return compare_evidence_lifecycle_replays(left, right).accepted


__all__ = ["EvidenceLifecycleReplayComparison", "EvidenceLifecycleReplayReceipt", "compare_evidence_lifecycle_replays", "evidence_lifecycle_replay_is_deterministic", "replay_evidence_lifecycle"]
