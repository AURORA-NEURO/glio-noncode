"""Replay expectations and deterministic receipt checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_fixture_eval import evaluate_lifecycle_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReplayCheck:
    check_id: str
    record_id: str | None
    passed: bool
    expected_address: str
    observed_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReplayReport:
    replay_id: str
    fixture_id: str
    checks: tuple[LifecycleBetaFrontierReplayCheck, ...]
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_lifecycle_beta_frontier_evaluation(fixture: LifecycleBetaFrontierFixture, baseline: LifecycleBetaFrontierEvaluation | None = None, *, replay_id: str = "lifecycle-beta-frontier-replay") -> LifecycleBetaFrontierReplayReport:
    baseline = baseline or evaluate_lifecycle_beta_frontier_fixture(fixture)
    replay = evaluate_lifecycle_beta_frontier_fixture(fixture)
    checks = []
    for old, new in zip(baseline.executions, replay.executions, strict=True):
        body = {"check_id": old.record_id, "record_id": old.record_id, "passed": old.content_address == new.content_address, "expected_address": old.content_address, "observed_address": new.content_address, "detail": "same fixture produces the same execution receipt"}
        checks.append(LifecycleBetaFrontierReplayCheck(**body, content_address=content_hash(body)))
    body = {"replay_id": replay_id, "fixture_id": fixture.fixture_id, "checks": tuple(checks), "deterministic": all(item.passed for item in checks)}
    return LifecycleBetaFrontierReplayReport(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierReplayCheck", "LifecycleBetaFrontierReplayReport", "replay_lifecycle_beta_frontier_evaluation"]
