"""Scenario transitions for accepted and reviewable Domain 04 paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_coordinate_fixture_eval import evaluate_reference_coordinate_fixture
from .reference_coordinate_public_data import (
    ReferenceCoordinateFixtureCatalog,
    ReferenceCoordinateRole,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateScenarioResult:
    scenario_id: str
    record_id: str
    operation: str
    role: ReferenceCoordinateRole
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateScenarioReport:
    fixture_id: str
    state: str
    results: tuple[ReferenceCoordinateScenarioResult, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(result.passed for result in self.results)

    @property
    def failed_scenario_ids(self) -> tuple[str, ...]:
        return tuple(result.scenario_id for result in self.results if not result.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_scenario_ids": self.failed_scenario_ids,
            "scenario_count": len(self.results),
        }


def evaluate_reference_coordinate_scenarios(
    catalog: ReferenceCoordinateFixtureCatalog,
) -> ReferenceCoordinateScenarioReport:
    """Evaluate each fixture row as an independently named state transition."""

    evaluation = evaluate_reference_coordinate_fixture(catalog)
    receipts_by_record = {receipt.record_id: receipt for receipt in evaluation.receipts}
    results: list[ReferenceCoordinateScenarioResult] = []
    for record in catalog.records:
        receipt = receipts_by_record[record.record_id]
        expected_issues = tuple(record.expected_issue_codes)
        observed_issues = tuple(receipt.issue_codes)
        passed = receipt.state == record.expected_state and observed_issues == expected_issues
        body = {
            "scenario_id": record.record_id,
            "record_id": record.record_id,
            "operation": record.operation,
            "role": record.role,
            "expected_state": record.expected_state,
            "observed_state": receipt.state,
            "expected_issue_codes": expected_issues,
            "observed_issue_codes": observed_issues,
            "passed": passed,
        }
        results.append(
            ReferenceCoordinateScenarioResult(
                scenario_id=record.record_id,
                record_id=record.record_id,
                operation=record.operation.value,
                role=record.role,
                expected_state=record.expected_state.value,
                observed_state=receipt.state.value,
                expected_issue_codes=expected_issues,
                observed_issue_codes=observed_issues,
                passed=passed,
                content_address=content_hash(body),
            )
        )
    state = "accepted" if all(result.passed for result in results) else "review"
    body = {"fixture_id": catalog.fixture_id, "state": state, "results": results}
    return ReferenceCoordinateScenarioReport(
        fixture_id=catalog.fixture_id,
        state=state,
        results=tuple(results),
        content_address=content_hash(body),
    )


__all__ = [
    "ReferenceCoordinateScenarioReport",
    "ReferenceCoordinateScenarioResult",
    "evaluate_reference_coordinate_scenarios",
]
