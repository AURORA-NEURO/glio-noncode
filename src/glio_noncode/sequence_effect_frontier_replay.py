"""Replay and drift checks for sequence-effect evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_fixture_eval import (
    SequenceEffectEvaluation,
    evaluate_sequence_effect_fixture,
)
from .sequence_effect_frontier_public_data import SequenceEffectFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectReplayCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"check_id": self.check_id, "passed": self.passed, "detail": self.detail}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectReplayReport:
    replay_id: str
    accepted: bool
    checks: tuple[SequenceEffectReplayCheck, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"replay_id": self.replay_id, "accepted": self.accepted, "checks": self.checks}
                ),
            )

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }


def replay_sequence_effect_evaluation(
    evaluation: SequenceEffectEvaluation,
    fixture: SequenceEffectFixture,
    replay_id: str = "sequence-effect-replay",
) -> SequenceEffectReplayReport:
    expected = evaluate_sequence_effect_fixture(fixture)
    checks = (
        SequenceEffectReplayCheck(
            "fixture-address",
            evaluation.fixture_address == fixture.content_address,
            "evaluation references the fixture",
        ),
        SequenceEffectReplayCheck(
            "evaluation-address",
            evaluation.content_address == expected.content_address,
            "evaluation address is deterministic",
        ),
        SequenceEffectReplayCheck(
            "execution-count",
            len(evaluation.executions) == len(expected.executions),
            "execution count is stable",
        ),
        SequenceEffectReplayCheck(
            "check-count", len(evaluation.checks) == len(expected.checks), "check count is stable"
        ),
        SequenceEffectReplayCheck(
            "execution-ids",
            tuple(item.record_id for item in evaluation.executions)
            == tuple(item.record_id for item in expected.executions),
            "execution ordering is stable",
        ),
        SequenceEffectReplayCheck(
            "states",
            tuple(item.adapter_state for item in evaluation.executions)
            == tuple(item.adapter_state for item in expected.executions),
            "states replay exactly",
        ),
        SequenceEffectReplayCheck(
            "outputs",
            tuple(item.content_address for item in evaluation.executions)
            == tuple(item.content_address for item in expected.executions),
            "outputs replay exactly",
        ),
        SequenceEffectReplayCheck(
            "accepted", evaluation.accepted == expected.accepted, "acceptance status is stable"
        ),
    )
    return SequenceEffectReplayReport(replay_id, all(item.passed for item in checks), checks)


__all__ = [
    "SequenceEffectReplayCheck",
    "SequenceEffectReplayReport",
    "replay_sequence_effect_evaluation",
]
