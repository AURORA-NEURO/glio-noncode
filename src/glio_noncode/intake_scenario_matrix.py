"""Independent positive/review scenario matrix for Domain 01 intake."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .intake_fixture_eval import (
    IntakeFixtureEvaluator,
    _issue_codes,
    _serialize_output,
    _state_value,
)
from .intake_public_data import (
    IntakeDataState,
    IntakeFixtureCatalog,
    IntakeFixtureRecord,
)
from .serialization import content_hash, jsonable, require_non_empty


class IntakeScenarioClass(StrEnum):
    """Whether a scenario exercises a normal path or a review boundary."""

    POSITIVE = "positive"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class IntakeScenario:
    """One operation payload and its expected state transition."""

    scenario_id: str
    scenario_class: IntakeScenarioClass
    record: IntakeFixtureRecord
    expected_state: str
    required_issue_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.expected_state, "expected_state")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeScenarioResult:
    """Observed state, issue codes, and deterministic receipt for one scenario."""

    scenario_id: str
    scenario_class: str
    expected_state: str
    observed_state: str
    required_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeScenarioMatrixReport:
    """Complete state-transition verdict for all fixture scenarios."""

    fixture_id: str
    context_key: str
    results: tuple[IntakeScenarioResult, ...]
    positive_scenario_ids: tuple[str, ...]
    review_scenario_ids: tuple[str, ...]
    failed_scenario_ids: tuple[str, ...]
    state: IntakeDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == IntakeDataState.ACCEPTED and not self.failed_scenario_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["scenario_count"] = len(self.results)
        result["positive_count"] = len(self.positive_scenario_ids)
        result["review_count"] = len(self.review_scenario_ids)
        return result


class IntakeScenarioMatrix:
    """Derive and independently execute four positive and all review controls."""

    def __init__(self, raw: Mapping[str, Any]) -> None:
        self.raw = raw
        self.catalog = IntakeFixtureCatalog.from_fixture(raw)
        self.evaluator = IntakeFixtureEvaluator()
        self.context = _context_mapping(raw.get("context"))

    @classmethod
    def from_file(cls, path: str | Path) -> IntakeScenarioMatrix:
        fixture_path = Path(path)
        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValidationError(f"unable to read intake scenario fixture: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"intake scenario fixture is not valid JSON: {path}") from exc
        if not isinstance(raw, Mapping):
            raise ValidationError("intake scenario fixture must be an object")
        return cls(raw)

    def scenarios(self) -> tuple[IntakeScenario, ...]:
        scenarios: list[IntakeScenario] = []
        for record in self.catalog.records:
            scenarios.append(
                IntakeScenario(
                    record.record_id,
                    IntakeScenarioClass.POSITIVE,
                    record,
                    record.expected_state,
                )
            )
        for control in self.catalog.controls:
            scenarios.append(
                IntakeScenario(
                    f"negative:{control.control_id}",
                    IntakeScenarioClass.REVIEW,
                    control.as_record(),
                    control.expected_state,
                    control.required_issue_codes,
                )
            )
        return tuple(scenarios)

    def run(self) -> IntakeScenarioMatrixReport:
        results: list[IntakeScenarioResult] = []
        for scenario in self.scenarios():
            output = self.evaluator.run_record(
                scenario.record,
                self.context,
                self.catalog.context_key,
            )
            serialized = _serialize_output(output)
            observed_state = _state_value(output)
            observed_issue_codes = _issue_codes(serialized)
            state_ok = observed_state == scenario.expected_state
            reasons_ok = all(code in observed_issue_codes for code in scenario.required_issue_codes)
            results.append(
                IntakeScenarioResult(
                    scenario.scenario_id,
                    scenario.scenario_class.value,
                    scenario.expected_state,
                    observed_state,
                    scenario.required_issue_codes,
                    observed_issue_codes,
                    state_ok and reasons_ok,
                    content_hash(
                        {
                            "scenario": scenario,
                            "state": observed_state,
                            "issue_codes": observed_issue_codes,
                            "output": serialized,
                        }
                    ),
                )
            )
        positive_ids = tuple(
            result.scenario_id
            for result in results
            if result.scenario_class == IntakeScenarioClass.POSITIVE.value
        )
        review_ids = tuple(
            result.scenario_id
            for result in results
            if result.scenario_class == IntakeScenarioClass.REVIEW.value
        )
        failed_ids = tuple(result.scenario_id for result in results if not result.passed)
        state = IntakeDataState.ACCEPTED if not failed_ids else IntakeDataState.REVIEW
        return IntakeScenarioMatrixReport(
            self.catalog.fixture_id,
            self.catalog.context_key,
            tuple(results),
            positive_ids,
            review_ids,
            failed_ids,
            state,
            content_hash(
                {
                    "fixture_id": self.catalog.fixture_id,
                    "context_key": self.catalog.context_key,
                    "results": results,
                }
            ),
        )


def _context_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValidationError("intake scenario context must be an object")
    fields = (
        "genome_build",
        "disease_class",
        "age_group",
        "cell_state",
        "territory",
        "treatment_phase",
    )
    return {
        field: require_non_empty(str(value.get(field, "")), f"context.{field}")
        for field in fields
    }


def evaluate_intake_scenarios(path: str | Path) -> IntakeScenarioMatrixReport:
    """Run the independent intake state-transition matrix."""

    return IntakeScenarioMatrix.from_file(path).run()


__all__ = [
    "IntakeScenario",
    "IntakeScenarioClass",
    "IntakeScenarioMatrix",
    "IntakeScenarioMatrixReport",
    "IntakeScenarioResult",
    "evaluate_intake_scenarios",
]
