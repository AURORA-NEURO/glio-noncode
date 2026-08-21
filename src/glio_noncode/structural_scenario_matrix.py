"""Independent state-transition scenarios for the Domain 02 structural gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .structural_fixture_eval import StructuralExecution, _execute
from .structural_public_data import (
    StructuralFixtureCatalog,
    StructuralFixtureRecord,
    StructuralFixtureState,
)


@dataclass(frozen=True, slots=True)
class StructuralScenarioResult:
    """Observed state and issue contract for one scenario."""

    scenario_id: str
    record_id: str
    operation: str
    expected_state: StructuralFixtureState
    observed_state: StructuralFixtureState
    expected_result_state: str
    observed_result_state: str
    required_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    output_address: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralScenarioMatrix:
    """All positive and review-boundary scenarios derived from a fixture."""

    fixture_id: str
    context_key: str
    scenarios: tuple[StructuralScenarioResult, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return bool(self.scenarios) and all(item.passed for item in self.scenarios)

    @property
    def positive_count(self) -> int:
        return sum(item.expected_state == StructuralFixtureState.ACCEPTED for item in self.scenarios)

    @property
    def review_count(self) -> int:
        return sum(item.expected_state == StructuralFixtureState.REVIEW for item in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["scenario_count"] = len(self.scenarios)
        result["positive_count"] = self.positive_count
        result["review_count"] = self.review_count
        return result


def evaluate_structural_scenarios(
    fixture: StructuralFixtureCatalog | str,
) -> StructuralScenarioMatrix:
    """Execute each fixture record separately and compare its declared contract."""

    catalog = (
        StructuralFixtureCatalog.from_file(fixture)
        if isinstance(fixture, str)
        else fixture
    )
    scenarios: list[StructuralScenarioResult] = []
    for record in catalog.positives + catalog.controls:
        execution = _execute(record, catalog.context_key)
        scenarios.append(_scenario(record, execution))
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "scenarios": scenarios,
    }
    return StructuralScenarioMatrix(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        scenarios=tuple(scenarios),
        content_address=content_hash(body),
    )


def _scenario(
    record: StructuralFixtureRecord,
    execution: StructuralExecution,
) -> StructuralScenarioResult:
    observed_codes = set(execution.issue_codes)
    passed = (
        execution.state == record.expected_state
        and execution.result_state == record.expected_result_state
        and set(record.required_issue_codes).issubset(observed_codes)
        and execution.output_address.startswith("sha256:")
    )
    return StructuralScenarioResult(
        scenario_id=f"scenario:{record.record_id}",
        record_id=record.record_id,
        operation=record.operation.value,
        expected_state=record.expected_state,
        observed_state=execution.state,
        expected_result_state=record.expected_result_state,
        observed_result_state=execution.result_state,
        required_issue_codes=record.required_issue_codes,
        observed_issue_codes=execution.issue_codes,
        output_address=execution.output_address,
        passed=passed,
        detail=execution.detail,
    )


__all__ = [
    "StructuralScenarioMatrix",
    "StructuralScenarioResult",
    "evaluate_structural_scenarios",
]
