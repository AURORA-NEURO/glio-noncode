"""Independent scenario matrix for Domain 02 C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .structural_beta_fixture_eval import _checks_for_record, _execute
from .structural_beta_public_data import (
    StructuralBetaFixtureCatalog,
    StructuralBetaFixtureState,
    StructuralBetaOperation,
)


@dataclass(frozen=True, slots=True)
class StructuralBetaScenarioResult:
    """One independent positive or review scenario result."""

    scenario_id: str
    record_id: str
    scenario_class: str
    operation: StructuralBetaOperation
    expected_state: StructuralBetaFixtureState
    observed_state: StructuralBetaFixtureState
    expected_result_state: str
    observed_result_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    counts: dict[str, int]
    passed: bool
    output_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralBetaScenarioMatrix:
    """Full independent matrix for all beta fixture records."""

    fixture_id: str
    context_key: str
    scenarios: tuple[StructuralBetaScenarioResult, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return bool(self.scenarios) and all(item.passed for item in self.scenarios)

    @property
    def positive_count(self) -> int:
        return sum(item.scenario_class == "positive" for item in self.scenarios)

    @property
    def review_count(self) -> int:
        return sum(item.scenario_class == "review" for item in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["scenario_count"] = len(self.scenarios)
        result["positive_count"] = self.positive_count
        result["review_count"] = self.review_count
        return result


def evaluate_structural_beta_scenarios(
    fixture: StructuralBetaFixtureCatalog | str,
) -> StructuralBetaScenarioMatrix:
    """Execute every beta record independently from the aggregate evaluator."""

    catalog = (
        StructuralBetaFixtureCatalog.from_file(fixture)
        if isinstance(fixture, str)
        else fixture
    )
    scenarios: list[StructuralBetaScenarioResult] = []
    for scenario_class, records in (("positive", catalog.positives), ("review", catalog.controls)):
        for record in records:
            execution = _execute(record)
            checks = _checks_for_record(record, execution)
            observed_state = (
                StructuralBetaFixtureState.ACCEPTED
                if record.expected_state == StructuralBetaFixtureState.ACCEPTED
                and all(check.passed for check in checks if check.check_kind == "state")
                else StructuralBetaFixtureState.REVIEW
            )
            scenarios.append(
                StructuralBetaScenarioResult(
                    scenario_id=f"{scenario_class}:{record.record_id}",
                    record_id=record.record_id,
                    scenario_class=scenario_class,
                    operation=record.operation,
                    expected_state=record.expected_state,
                    observed_state=observed_state,
                    expected_result_state=record.expected_result_state,
                    observed_result_state=execution.observed_result_state,
                    expected_issue_codes=record.required_issue_codes,
                    observed_issue_codes=execution.issue_codes,
                    counts=dict(execution.counts),
                    passed=all(check.passed for check in checks),
                    output_address=execution.output_address,
                    detail=execution.detail,
                )
            )
    ordered = tuple(sorted(scenarios, key=lambda item: item.scenario_id))
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "scenarios": ordered,
    }
    return StructuralBetaScenarioMatrix(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        scenarios=ordered,
        content_address=content_hash(body),
    )


__all__ = [
    "StructuralBetaScenarioMatrix",
    "StructuralBetaScenarioResult",
    "evaluate_structural_beta_scenarios",
]
