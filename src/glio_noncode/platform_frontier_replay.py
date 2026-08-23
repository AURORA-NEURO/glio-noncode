"""Replay and address comparison for platform evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierFixture
from .platform_frontier_fixture_eval import evaluate_platform_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierReplayCheck:
    record_id: str
    original_address: str
    replay_address: str
    matched: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierReplayReport:
    fixture_id: str
    checks: tuple[PlatformFrontierReplayCheck, ...]
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_platform_frontier_evaluation(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation) -> PlatformFrontierReplayReport:
    replay = evaluate_platform_frontier_fixture(fixture)
    checks = []
    for original, repeated in zip(evaluation.executions, replay.executions, strict=True):
        body = {"record_id": original.record_id, "original_address": original.content_address, "replay_address": repeated.content_address, "matched": original.content_address == repeated.content_address}
        checks.append(PlatformFrontierReplayCheck(**body, content_address=content_hash(body)))
    deterministic = all(item.matched for item in checks)
    return PlatformFrontierReplayReport(fixture.fixture_id, tuple(checks), deterministic, deterministic and replay.accepted, content_hash(tuple(checks)))


__all__ = ["PlatformFrontierReplayCheck", "PlatformFrontierReplayReport", "replay_platform_frontier_evaluation"]
