"""Scenario matrix for positive and review transitions in C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .specimen_preanalytic_fixture_eval import evaluate_specimen_preanalytic_fixture
from .specimen_preanalytic_public_data import SpecimenPreanalyticFixtureCatalog


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticScenarioResult:
    scenario_id: str
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario ID")
        require_non_empty(self.record_id, "scenario record ID")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("scenario must be content-addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticScenarioReport:
    fixture_id: str
    scenarios: tuple[SpecimenPreanalyticScenarioResult, ...]
    positive_count: int
    control_count: int
    state: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(item.passed for item in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "scenario_count": len(self.scenarios),
            "passed": self.passed,
        }


def evaluate_specimen_preanalytic_scenarios(
    catalog: SpecimenPreanalyticFixtureCatalog,
) -> SpecimenPreanalyticScenarioReport:
    """Project every fixture receipt into an explicit state transition row."""

    evaluation = evaluate_specimen_preanalytic_fixture(catalog)
    scenarios: list[SpecimenPreanalyticScenarioResult] = []
    for receipt in evaluation.receipts:
        body = {
            "record_id": receipt.record_id,
            "operation": receipt.operation,
            "expected_state": receipt.expected_state,
            "observed_state": receipt.observed_state,
            "issue_codes": receipt.issue_codes,
        }
        scenarios.append(
            SpecimenPreanalyticScenarioResult(
                scenario_id=f"scenario:{receipt.record_id}",
                record_id=receipt.record_id,
                operation=receipt.operation,
                role=receipt.role,
                expected_state=receipt.expected_state,
                observed_state=receipt.observed_state,
                issue_codes=receipt.issue_codes,
                passed=receipt.passed,
                content_address=content_hash(body),
            )
        )
    state = (
        "accepted"
        if all(item.passed for item in scenarios) and len(scenarios) == len(catalog.records)
        else "review"
    )
    body = {
        "fixture_id": catalog.fixture_id,
        "scenarios": scenarios,
        "state": state,
    }
    return SpecimenPreanalyticScenarioReport(
        catalog.fixture_id,
        tuple(scenarios),
        sum(item.role == "positive" for item in scenarios),
        sum(item.role == "control" for item in scenarios),
        state,
        content_hash(body),
    )


__all__ = [
    "SpecimenPreanalyticScenarioReport",
    "SpecimenPreanalyticScenarioResult",
    "evaluate_specimen_preanalytic_scenarios",
]
