"""Independent state-transition scenarios for Domain 02 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .structural_frontier_fixture_eval import _execute, _observed_fixture_state
from .structural_frontier_public_data import (
    StructuralFrontierFixtureCatalog,
    StructuralFrontierFixtureState,
    StructuralFrontierOperation,
)


@dataclass(frozen=True, slots=True)
class StructuralFrontierScenarioResult:
    """Result of one independently executed fixture transition."""

    scenario_id: str
    operation: StructuralFrontierOperation
    expected_fixture_state: StructuralFrontierFixtureState
    observed_fixture_state: StructuralFrontierFixtureState
    expected_result_state: str
    observed_result_state: str
    issue_codes: tuple[str, ...]
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierScenarioMatrix:
    """Complete independent scenario matrix."""

    scenarios: tuple[StructuralFrontierScenarioResult, ...]
    positive_count: int
    review_count: int
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"scenario_count": len(self.scenarios)}


def evaluate_structural_frontier_scenarios(
    fixture: StructuralFrontierFixtureCatalog | str,
) -> StructuralFrontierScenarioMatrix:
    """Run each positive and control as an independent state transition."""

    catalog = StructuralFrontierFixtureCatalog.from_file(fixture) if isinstance(fixture, str) else fixture
    scenarios: list[StructuralFrontierScenarioResult] = []
    for record in catalog.positives + catalog.controls:
        execution = _execute(record)
        observed_state = _observed_fixture_state(record, execution)
        expected_issues = set(record.required_issue_codes)
        observed_issues = set(execution.issue_codes)
        passed = (
            observed_state == record.expected_state
            and execution.observed_result_state == record.expected_result_state
            and expected_issues.issubset(observed_issues)
        )
        scenarios.append(
            StructuralFrontierScenarioResult(
                scenario_id=f"scenario:{record.record_id}",
                operation=record.operation,
                expected_fixture_state=record.expected_state,
                observed_fixture_state=observed_state,
                expected_result_state=record.expected_result_state,
                observed_result_state=execution.observed_result_state,
                issue_codes=execution.issue_codes,
                passed=passed,
                detail=execution.detail,
            )
        )
    positives = sum(item.expected_fixture_state == StructuralFrontierFixtureState.ACCEPTED for item in scenarios)
    reviews = sum(item.expected_fixture_state == StructuralFrontierFixtureState.REVIEW for item in scenarios)
    passed = bool(scenarios) and all(item.passed for item in scenarios)
    body = {
        "scenarios": scenarios,
        "positive_count": positives,
        "review_count": reviews,
        "passed": passed,
    }
    return StructuralFrontierScenarioMatrix(
        scenarios=tuple(scenarios),
        positive_count=positives,
        review_count=reviews,
        passed=passed,
        content_address=content_hash(body),
    )


__all__ = [
    "StructuralFrontierScenarioMatrix",
    "StructuralFrontierScenarioResult",
    "evaluate_structural_frontier_scenarios",
]
