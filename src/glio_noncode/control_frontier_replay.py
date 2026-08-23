"""Deterministic replay receipt for control frontier evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierFixture
from .control_frontier_fixture_eval import evaluate_control_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierReplayCheck:
    record_id: str
    expected_address: str
    replayed_address: str
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierReplayReport:
    fixture_id: str
    checks: tuple[ControlFrontierReplayCheck, ...]
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_control_frontier_evaluation(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation) -> ControlFrontierReplayReport:
    replayed = evaluate_control_frontier_fixture(fixture)
    checks = []
    for expected, actual in zip(evaluation.executions, replayed.executions, strict=True):
        body = {"record_id": expected.record_id, "expected_address": expected.content_address, "replayed_address": actual.content_address, "passed": expected.content_address == actual.content_address}
        checks.append(ControlFrontierReplayCheck(**body, content_address=content_hash(body)))
    return ControlFrontierReplayReport(fixture.fixture_id, tuple(checks), all(item.passed for item in checks) and evaluation.content_address == replayed.content_address, content_hash(tuple(checks)))


__all__ = ["ControlFrontierReplayCheck", "ControlFrontierReplayReport", "replay_control_frontier_evaluation"]
