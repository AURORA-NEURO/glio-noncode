"""Deterministic replay checks for the sequence grammar fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import (
    SequenceGrammarEvaluation,
    evaluate_sequence_grammar_fixture,
)
from .sequence_grammar_frontier_public_data import SequenceGrammarFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarReplayCheck:
    check_id: str
    passed: bool
    expected: str
    observed: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.detail.strip():
            raise ValidationError("replay check is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "check_id": self.check_id,
                        "passed": self.passed,
                        "expected": self.expected,
                        "observed": self.observed,
                        "detail": self.detail,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarReplayReport:
    accepted: bool
    checks: tuple[SequenceGrammarReplayCheck, ...]
    fixture_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.checks) != 8:
            raise ValidationError("eight replay checks are required")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "checks": self.checks,
                        "fixture_id": self.fixture_id,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "check_count": len(self.checks),
            "checks": [check.to_dict() for check in self.checks],
            "content_address": self.content_address,
        }


def replay_sequence_grammar_evaluation(
    evaluation: SequenceGrammarEvaluation, fixture: SequenceGrammarFixture
) -> SequenceGrammarReplayReport:
    repeated = evaluate_sequence_grammar_fixture(fixture)
    checks = (
        SequenceGrammarReplayCheck(
            "address",
            evaluation.content_address == repeated.content_address,
            evaluation.content_address,
            repeated.content_address,
            "evaluation address is deterministic",
        ),
        SequenceGrammarReplayCheck(
            "accepted",
            evaluation.accepted == repeated.accepted,
            str(evaluation.accepted),
            str(repeated.accepted),
            "accepted state is deterministic",
        ),
        SequenceGrammarReplayCheck(
            "execution-count",
            len(evaluation.executions) == len(repeated.executions),
            str(len(evaluation.executions)),
            str(len(repeated.executions)),
            "execution count is deterministic",
        ),
        SequenceGrammarReplayCheck(
            "check-count",
            len(evaluation.checks) == len(repeated.checks),
            str(len(evaluation.checks)),
            str(len(repeated.checks)),
            "check count is deterministic",
        ),
        SequenceGrammarReplayCheck(
            "states",
            tuple(row.adapter_state.value for row in evaluation.executions)
            == tuple(row.adapter_state.value for row in repeated.executions),
            "ordered states",
            "ordered states",
            "state sequence is deterministic",
        ),
        SequenceGrammarReplayCheck(
            "issues",
            tuple(row.issue_codes for row in evaluation.executions)
            == tuple(row.issue_codes for row in repeated.executions),
            "ordered issue codes",
            "ordered issue codes",
            "issue sequence is deterministic",
        ),
        SequenceGrammarReplayCheck(
            "records",
            tuple(row.record_id for row in evaluation.executions)
            == tuple(row.record_id for row in repeated.executions),
            "ordered record IDs",
            "ordered record IDs",
            "record order is deterministic",
        ),
        SequenceGrammarReplayCheck(
            "fixture",
            evaluation.fixture_id == repeated.fixture_id,
            evaluation.fixture_id,
            repeated.fixture_id,
            "fixture identity is conserved",
        ),
    )
    return SequenceGrammarReplayReport(
        all(check.passed for check in checks), checks, fixture.fixture_id
    )


__all__ = [
    "SequenceGrammarReplayCheck",
    "SequenceGrammarReplayReport",
    "replay_sequence_grammar_evaluation",
]
