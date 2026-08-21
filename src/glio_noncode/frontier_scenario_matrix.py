"""Scenario matrix runner for accepted and review frontier paths.

The fixture evaluator proves that the full contract passes. This module makes
the expected state transitions independently inspectable: every positive
pipeline has an accepted scenario, and every declared negative control has a
review scenario with required blocked stages. The matrix is useful for local
regression triage because it reports the first scenario that changes state.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import FrontierState
from .frontier_end_to_end import run_end_to_end_operation
from .serialization import content_hash, jsonable, require_non_empty


class ScenarioExpectation(StrEnum):
    """Expected outcome class for one matrix scenario."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class FrontierScenario:
    """One operation payload and its expected state boundary."""

    scenario_id: str
    operation: str
    expected_state: ScenarioExpectation
    payload: Mapping[str, Any]
    expected_blocked_stage_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.operation, "operation")
        if not isinstance(self.payload, Mapping):
            raise ValidationError(f"{self.scenario_id} payload must be an object")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierScenarioResult:
    """Observed state and blocked stages for one scenario."""

    scenario_id: str
    operation: str
    expected_state: str
    observed_state: str
    expected_blocked_stage_ids: tuple[str, ...]
    observed_blocked_stage_ids: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierScenarioMatrixReport:
    """Complete scenario matrix verdict."""

    context_key: str
    results: tuple[FrontierScenarioResult, ...]
    accepted_scenario_ids: tuple[str, ...]
    review_scenario_ids: tuple[str, ...]
    failed_scenario_ids: tuple[str, ...]
    state: FrontierState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == FrontierState.ACCEPTED and not self.failed_scenario_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["scenario_count"] = len(self.results)
        return result


class FrontierScenarioMatrix:
    """Build and run the positive/negative scenarios declared in a fixture."""

    _positive_operations = (
        ("validation-positive", "run-validation-frontier-pipeline", "validation"),
        ("evidence-positive", "run-evidence-lifecycle-pipeline", "evidence"),
        ("workbench-positive", "run-workbench-quality-pipeline", "workbench"),
        ("deployment-positive", "run-deployment-governance-pipeline", "deployment"),
    )

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        self.fixture = fixture
        self.context_key = self._context_key(fixture.get("context"))

    @classmethod
    def from_file(cls, path: str | Path) -> FrontierScenarioMatrix:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("scenario fixture must be an object")
        return cls(raw)

    @staticmethod
    def _context_key(value: Any) -> str:
        if not isinstance(value, Mapping):
            raise ValidationError("scenario fixture context must be an object")
        fields = (
            "genome_build",
            "disease_class",
            "age_group",
            "cell_state",
            "territory",
            "treatment_phase",
        )
        values = tuple(
            require_non_empty(str(value.get(field, "")), f"context.{field}")
            for field in fields
        )
        return "|".join(values)

    def scenarios(self) -> tuple[FrontierScenario, ...]:
        pipelines = self.fixture.get("pipelines")
        if not isinstance(pipelines, Mapping):
            raise ValidationError("scenario fixture pipelines must be an object")
        scenarios: list[FrontierScenario] = []
        for scenario_id, operation, pipeline_name in self._positive_operations:
            payload = dict(pipelines.get(pipeline_name, {}))
            payload["pipeline_id"] = f"fixture-matrix:{pipeline_name}"
            scenarios.append(
                FrontierScenario(
                    scenario_id,
                    operation,
                    ScenarioExpectation.ACCEPTED,
                    payload,
                )
            )
        controls = self.fixture.get("negative_controls", ())
        if not isinstance(controls, Sequence) or isinstance(controls, (str, bytes)):
            raise ValidationError("scenario fixture negative_controls must be an array")
        for control in controls:
            if not isinstance(control, Mapping):
                raise ValidationError("scenario negative control must be an object")
            scenario_id = require_non_empty(str(control.get("check_id", "")), "check_id")
            operation = require_non_empty(str(control.get("operation", "")), "operation")
            payload = control.get("payload")
            if not isinstance(payload, Mapping):
                raise ValidationError(f"{scenario_id} payload must be an object")
            scenarios.append(
                FrontierScenario(
                    f"negative:{scenario_id}",
                    operation,
                    ScenarioExpectation.REVIEW,
                    payload,
                    tuple(str(item) for item in control.get("expected_blocked_stage_ids", ())),
                )
            )
        return tuple(scenarios)

    def run(self) -> FrontierScenarioMatrixReport:
        results: list[FrontierScenarioResult] = []
        for scenario in self.scenarios():
            report = run_end_to_end_operation(
                scenario.operation,
                scenario.payload,
                context_key=self.context_key,
            )
            observed_state = str(getattr(report, "state", "review"))
            observed_blocked = tuple(str(item) for item in getattr(report, "blocked_stage_ids", ()))
            blocked_ok = set(scenario.expected_blocked_stage_ids).issubset(set(observed_blocked))
            passed = observed_state == scenario.expected_state.value and blocked_ok
            results.append(
                FrontierScenarioResult(
                    scenario.scenario_id,
                    scenario.operation,
                    scenario.expected_state.value,
                    observed_state,
                    scenario.expected_blocked_stage_ids,
                    observed_blocked,
                    passed,
                    content_hash(
                        {
                            "scenario": scenario,
                            "state": observed_state,
                            "blocked": observed_blocked,
                        }
                    ),
                )
            )
        accepted = tuple(
            result.scenario_id
            for result in results
            if result.observed_state == ScenarioExpectation.ACCEPTED.value
        )
        review = tuple(
            result.scenario_id
            for result in results
            if result.observed_state == ScenarioExpectation.REVIEW.value
        )
        failed = tuple(result.scenario_id for result in results if not result.passed)
        state = FrontierState.ACCEPTED if not failed else FrontierState.REVIEW
        return FrontierScenarioMatrixReport(
            self.context_key,
            tuple(results),
            accepted,
            review,
            failed,
            state,
            content_hash({"context_key": self.context_key, "results": results}),
        )


def evaluate_frontier_scenarios(path: str | Path) -> FrontierScenarioMatrixReport:
    """Run the fixture scenario matrix from disk."""

    return FrontierScenarioMatrix.from_file(path).run()


__all__ = [
    "FrontierScenario",
    "FrontierScenarioMatrix",
    "FrontierScenarioMatrixReport",
    "FrontierScenarioResult",
    "ScenarioExpectation",
    "evaluate_frontier_scenarios",
]
