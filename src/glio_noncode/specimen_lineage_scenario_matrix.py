"""Independent scenario matrix for Domain 03 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable
from .specimen_lineage_fixture_eval import SpecimenLineageFixtureEvaluator
from .specimen_lineage_public_data import (
    SpecimenLineageFixtureCatalog,
)


@dataclass(frozen=True, slots=True)
class SpecimenLineageScenarioResult:
    """One independent row-level state transition result."""

    scenario_id: str
    operation: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    observed_counts: dict[str, int]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineageScenarioReport:
    """Complete independent matrix report."""

    fixture_id: str
    scenarios: tuple[SpecimenLineageScenarioResult, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return bool(self.scenarios) and all(item.passed for item in self.scenarios)

    @property
    def failed_scenarios(self) -> tuple[str, ...]:
        return tuple(item.scenario_id for item in self.scenarios if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_scenarios": self.failed_scenarios,
        }


def evaluate_specimen_lineage_scenarios(
    source: SpecimenLineageFixtureCatalog | str | Path,
) -> SpecimenLineageScenarioReport:
    """Execute each fixture row independently from the aggregate report."""

    catalog = (
        source
        if isinstance(source, SpecimenLineageFixtureCatalog)
        else SpecimenLineageFixtureCatalog.from_file(source)
    )
    evaluator = SpecimenLineageFixtureEvaluator()
    results: list[SpecimenLineageScenarioResult] = []
    for record in catalog.records:
        execution = evaluator._execute(record)
        expected_issues = tuple(sorted(record.expected_issue_codes))
        passed = (
            execution.observed_result_state == record.expected_result_state
            and execution.issue_codes == expected_issues
            and all(
                execution.counts.get(key) == value for key, value in record.expected_counts.items()
            )
        )
        results.append(
            SpecimenLineageScenarioResult(
                scenario_id=record.record_id,
                operation=record.operation.value,
                expected_state=record.expected_result_state,
                observed_state=execution.observed_result_state,
                expected_issue_codes=expected_issues,
                observed_issue_codes=execution.issue_codes,
                observed_counts=dict(execution.counts),
                passed=passed,
            )
        )
    body = {"fixture_id": catalog.fixture_id, "scenarios": results}
    return SpecimenLineageScenarioReport(
        fixture_id=catalog.fixture_id,
        scenarios=tuple(results),
        content_address=content_hash(body),
    )


__all__ = [
    "SpecimenLineageScenarioReport",
    "SpecimenLineageScenarioResult",
    "evaluate_specimen_lineage_scenarios",
]
