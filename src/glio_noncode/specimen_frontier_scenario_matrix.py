"""Independent scenario execution for Domain 03 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .specimen_frontier_fixture_eval import _execute, _observed_fixture_state
from .specimen_frontier_public_data import (
    SpecimenFrontierFixtureCatalog,
    SpecimenFrontierFixtureRecord,
    SpecimenFrontierFixtureState,
)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierScenarioResult:
    """Result of one independently executed specimen transition."""

    scenario_id: str
    record_id: str
    expected_state: SpecimenFrontierFixtureState
    observed_state: SpecimenFrontierFixtureState
    expected_result_state: str
    observed_result_state: str
    issue_codes: tuple[str, ...]
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierScenarioMatrix:
    """Complete independent scenario matrix."""

    fixture_id: str
    scenarios: tuple[SpecimenFrontierScenarioResult, ...]
    positive_count: int
    review_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return bool(self.scenarios) and all(scenario.passed for scenario in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "scenario_count": len(self.scenarios),
        }


def evaluate_specimen_frontier_scenarios(
    fixture: SpecimenFrontierFixtureCatalog | str,
) -> SpecimenFrontierScenarioMatrix:
    """Run each positive and control as an independent state transition."""

    catalog = (
        SpecimenFrontierFixtureCatalog.from_file(fixture) if isinstance(fixture, str) else fixture
    )
    scenarios: list[SpecimenFrontierScenarioResult] = []
    for record in catalog.positives + catalog.controls:
        scenarios.append(_run_scenario(record))
    body = {
        "fixture_id": catalog.fixture_id,
        "scenarios": scenarios,
        "positive_count": len(catalog.positives),
        "review_count": len(catalog.controls),
    }
    return SpecimenFrontierScenarioMatrix(
        fixture_id=catalog.fixture_id,
        scenarios=tuple(scenarios),
        positive_count=len(catalog.positives),
        review_count=len(catalog.controls),
        content_address=content_hash(body),
    )


def _run_scenario(record: SpecimenFrontierFixtureRecord) -> SpecimenFrontierScenarioResult:
    execution = _execute(record)
    expected_issue_codes = tuple(
        sorted(str(item) for item in record.parameters.get("required_issue_codes", ()))
    )
    observed_state = _observed_fixture_state(execution)
    passed = (
        observed_state == record.expected_state
        and execution.observed_result_state == record.expected_result_state
        and execution.issue_codes == expected_issue_codes
    )
    return SpecimenFrontierScenarioResult(
        scenario_id=f"scenario:{record.record_id}",
        record_id=record.record_id,
        expected_state=record.expected_state,
        observed_state=observed_state,
        expected_result_state=record.expected_result_state,
        observed_result_state=execution.observed_result_state,
        issue_codes=execution.issue_codes,
        passed=passed,
        detail=execution.detail,
    )


__all__ = [
    "SpecimenFrontierScenarioMatrix",
    "SpecimenFrontierScenarioResult",
    "evaluate_specimen_frontier_scenarios",
]
