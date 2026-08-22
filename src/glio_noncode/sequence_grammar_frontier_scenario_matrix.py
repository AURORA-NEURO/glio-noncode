"""Scenario matrix for positive, control, and boundary paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    SequenceGrammarOperation,
    SequenceGrammarState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarScenario:
    scenario_id: str
    operation: SequenceGrammarOperation
    required_state: SequenceGrammarState
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenario_id.strip() or not self.description.strip():
            raise ValidationError("scenario is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "scenario_id": self.scenario_id,
                        "operation": self.operation,
                        "required_state": self.required_state,
                        "description": self.description,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarScenarioResult:
    scenario_id: str
    matched_record_ids: tuple[str, ...]
    passed: bool
    observed_states: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "scenario_id": self.scenario_id,
                        "matched_record_ids": self.matched_record_ids,
                        "passed": self.passed,
                        "observed_states": self.observed_states,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarScenarioReport:
    accepted: bool
    scenarios: tuple[SequenceGrammarScenario, ...]
    results: tuple[SequenceGrammarScenarioResult, ...]
    fixture_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.scenarios) != len(self.results):
            raise ValidationError("scenario and result counts must match")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "scenarios": self.scenarios,
                        "results": self.results,
                        "fixture_id": self.fixture_id,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "scenario_count": len(self.scenarios),
            "scenarios": [item.to_dict() for item in self.scenarios],
            "results": [item.to_dict() for item in self.results],
            "content_address": self.content_address,
        }


def default_sequence_grammar_scenarios() -> tuple[SequenceGrammarScenario, ...]:
    rows = (
        (
            "C05-positive-loss",
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            SequenceGrammarState.SUPPORTED,
            "loss path retains reference-only hits",
        ),
        (
            "C05-invalid-window",
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            SequenceGrammarState.INVALID,
            "alphabet error is rejected",
        ),
        (
            "C05-empty-window",
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            SequenceGrammarState.ABSTAINED,
            "empty window abstains",
        ),
        (
            "C06-positive-gain",
            SequenceGrammarOperation.MOTIF_CREATION,
            SequenceGrammarState.SUPPORTED,
            "gain path retains alternate-only hits",
        ),
        (
            "C06-invalid-window",
            SequenceGrammarOperation.MOTIF_CREATION,
            SequenceGrammarState.INVALID,
            "alphabet error is rejected",
        ),
        (
            "C06-empty-catalog",
            SequenceGrammarOperation.MOTIF_CREATION,
            SequenceGrammarState.ABSTAINED,
            "empty catalog abstains",
        ),
        (
            "C07-compatible-pair",
            SequenceGrammarOperation.SPACING_GRAMMAR,
            SequenceGrammarState.SUPPORTED,
            "compatible spacing is retained",
        ),
        (
            "C07-unmatched-rule",
            SequenceGrammarOperation.SPACING_GRAMMAR,
            SequenceGrammarState.ABSTAINED,
            "unmatched rule abstains",
        ),
        (
            "C07-invalid-hit",
            SequenceGrammarOperation.SPACING_GRAMMAR,
            SequenceGrammarState.INVALID,
            "invalid interval is rejected",
        ),
        (
            "C08-supported-interaction",
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            SequenceGrammarState.SUPPORTED,
            "interaction contribution is retained",
        ),
        (
            "C08-missing-required",
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            SequenceGrammarState.ABSTAINED,
            "missing required interaction abstains",
        ),
        (
            "C08-invalid-sequence",
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            SequenceGrammarState.INVALID,
            "invalid sequence is rejected",
        ),
    )
    return tuple(
        SequenceGrammarScenario(scenario_id, operation, state, description)
        for scenario_id, operation, state, description in rows
    )


def evaluate_sequence_grammar_scenarios(
    fixture: SequenceGrammarFixture, evaluation: SequenceGrammarEvaluation
) -> SequenceGrammarScenarioReport:
    scenarios = default_sequence_grammar_scenarios()
    results: list[SequenceGrammarScenarioResult] = []
    for scenario in scenarios:
        matches = tuple(
            execution
            for execution in evaluation.executions
            if execution.operation is scenario.operation
            and execution.adapter_state is scenario.required_state
        )
        result = SequenceGrammarScenarioResult(
            scenario.scenario_id,
            tuple(item.record_id for item in matches),
            bool(matches),
            tuple(item.adapter_state.value for item in matches),
        )
        results.append(result)
    return SequenceGrammarScenarioReport(
        all(result.passed for result in results), scenarios, tuple(results), fixture.fixture_id
    )


__all__ = [
    "SequenceGrammarScenario",
    "SequenceGrammarScenarioReport",
    "SequenceGrammarScenarioResult",
    "default_sequence_grammar_scenarios",
    "evaluate_sequence_grammar_scenarios",
]
