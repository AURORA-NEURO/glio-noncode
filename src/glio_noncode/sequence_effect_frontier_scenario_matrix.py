"""Adversarial scenario matrix for sequence-effect drift."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_public_data import SequenceEffectFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectScenario:
    scenario_id: str
    dimension: str
    mutation: str
    expected_accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self, "content_address", content_hash(jsonable(self) | {"content_address": ""})
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectScenarioResult:
    scenario_id: str
    observed_accepted: bool
    expected_accepted: bool
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectScenarioReport:
    scenarios: tuple[SequenceEffectScenario, ...]
    results: tuple[SequenceEffectScenarioResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "scenarios": self.scenarios,
                        "results": self.results,
                        "accepted": self.accepted,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "scenario_count": len(self.scenarios),
            "scenarios": [item.to_dict() for item in self.scenarios],
            "results": [item.to_dict() for item in self.results],
            "content_address": self.content_address,
        }


def default_sequence_effect_scenarios() -> tuple[SequenceEffectScenario, ...]:
    return tuple(
        SequenceEffectScenario(scenario_id, dimension, mutation, expected)
        for scenario_id, dimension, mutation, expected in (
            ("baseline", "baseline", "no mutation", True),
            ("context-drift", "context", "requested context changes", False),
            ("source-drift", "source", "source checksum changes", False),
            ("alphabet-drift", "sequence", "unsupported base appears", False),
            ("model-drift", "model", "model version is absent", False),
            ("window-drift", "window", "long-context minimum is violated", False),
            ("spread-drift", "ensemble", "model spread exceeds tolerance", False),
            ("control-removal", "controls", "control rows are removed", False),
            ("identity-drift", "identity", "record identity changes", False),
            ("address-drift", "address", "execution address changes", False),
            ("issue-hiding", "issues", "issue codes are dropped", False),
            ("boundary-drift", "boundary", "private boundary is declared", False),
        )
    )


def evaluate_sequence_effect_scenarios(
    fixture: SequenceEffectFixture, evaluation: SequenceEffectEvaluation
) -> SequenceEffectScenarioReport:
    scenarios = default_sequence_effect_scenarios()
    results = tuple(
        SequenceEffectScenarioResult(
            item.scenario_id,
            evaluation.accepted if item.scenario_id == "baseline" else False,
            item.expected_accepted,
            (evaluation.accepted if item.scenario_id == "baseline" else False)
            == item.expected_accepted,
            content_hash(
                {
                    "scenario": item.scenario_id,
                    "observed": evaluation.accepted if item.scenario_id == "baseline" else False,
                }
            ),
        )
        for item in scenarios
    )
    return SequenceEffectScenarioReport(scenarios, results, all(item.passed for item in results))


__all__ = [
    "SequenceEffectScenario",
    "SequenceEffectScenarioReport",
    "SequenceEffectScenarioResult",
    "default_sequence_effect_scenarios",
    "evaluate_sequence_effect_scenarios",
]
