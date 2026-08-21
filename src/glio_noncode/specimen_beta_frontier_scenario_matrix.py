"""Independent state-transition scenarios for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable
from .specimen_beta_frontier_fixture_eval import SpecimenBetaFrontierFixtureEvaluator
from .specimen_beta_frontier_public_data import (
    SpecimenBetaFrontierFixtureCatalog,
    SpecimenBetaFrontierFixtureRecord,
)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierScenario:
    """One expected state transition for one fixture record."""

    scenario_id: str
    record_id: str
    operation: str
    fixture_state: str
    expected_result_state: str
    observed_result_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierScenarioMatrixReport:
    """Scenario report with operation and state coverage counts."""

    fixture_id: str
    scenarios: tuple[SpecimenBetaFrontierScenario, ...]
    positive_count: int
    control_count: int
    operation_count: int
    content_address: str

    @property
    def passed(self) -> bool:
        return bool(self.scenarios) and all(scenario.passed for scenario in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


def evaluate_specimen_beta_frontier_scenarios(
    source: str | Path | SpecimenBetaFrontierFixtureCatalog,
) -> SpecimenBetaFrontierScenarioMatrixReport:
    """Run twelve state scenarios without consuming the fixture check report."""

    catalog = (
        source
        if isinstance(source, SpecimenBetaFrontierFixtureCatalog)
        else SpecimenBetaFrontierFixtureCatalog.from_file(source)
    )
    evaluator = SpecimenBetaFrontierFixtureEvaluator()
    scenarios = tuple(_scenario(record, evaluator) for record in catalog.records)
    body = {
        "fixture_id": catalog.fixture_id,
        "scenarios": scenarios,
        "positive_count": len(catalog.positives),
        "control_count": len(catalog.controls),
        "operation_count": len(catalog.operation_ids),
    }
    return SpecimenBetaFrontierScenarioMatrixReport(
        fixture_id=catalog.fixture_id,
        scenarios=scenarios,
        positive_count=len(catalog.positives),
        control_count=len(catalog.controls),
        operation_count=len(catalog.operation_ids),
        content_address=content_hash(body),
    )


def _scenario(
    record: SpecimenBetaFrontierFixtureRecord,
    evaluator: SpecimenBetaFrontierFixtureEvaluator,
) -> SpecimenBetaFrontierScenario:
    execution = evaluator._execute(record)
    expected_issue_codes = tuple(sorted(record.expected_issue_codes))
    passed = (
        execution.observed_result_state == record.expected_result_state
        and execution.issue_codes == expected_issue_codes
    )
    return SpecimenBetaFrontierScenario(
        scenario_id=f"scenario:{record.record_id}",
        record_id=record.record_id,
        operation=record.operation.value,
        fixture_state=record.expected_fixture_state.value,
        expected_result_state=record.expected_result_state,
        observed_result_state=execution.observed_result_state,
        expected_issue_codes=expected_issue_codes,
        observed_issue_codes=execution.issue_codes,
        passed=passed,
    )


__all__ = [
    "SpecimenBetaFrontierScenario",
    "SpecimenBetaFrontierScenarioMatrixReport",
    "evaluate_specimen_beta_frontier_scenarios",
]
