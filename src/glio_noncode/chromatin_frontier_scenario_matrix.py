"""Positive and control scenario assertions for Domain 07."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_frontier_fixture_eval import (
    ChromatinFrontierEvaluationReport,
    evaluate_chromatin_frontier_fixture,
)
from .chromatin_frontier_public_data import (
    ChromatinFrontierOperation,
    ChromatinFrontierRole,
    default_chromatin_frontier_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinFrontierScenario:
    scenario_id: str
    operation: ChromatinFrontierOperation
    role: ChromatinFrontierRole
    record_id: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierScenarioCheck:
    scenario_id: str
    passed: bool
    observed_state: str
    observed_issue_codes: tuple[str, ...]
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierScenarioReport:
    fixture_id: str
    scenarios: tuple[ChromatinFrontierScenario, ...]
    checks: tuple[ChromatinFrontierScenarioCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.scenarios) and all(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def default_chromatin_frontier_scenarios() -> tuple[ChromatinFrontierScenario, ...]:
    fixture = default_chromatin_frontier_fixture()
    scenarios: list[ChromatinFrontierScenario] = []
    for record in fixture.records:
        body = {
            "scenario_id": f"scenario:{record.record_id}",
            "operation": record.operation,
            "role": record.role,
            "record_id": record.record_id,
            "expected_state": record.expected_state,
            "expected_issue_codes": record.expected_issue_codes,
            "detail": record.description,
        }
        scenarios.append(ChromatinFrontierScenario(**body, content_address=content_hash(body)))
    return tuple(scenarios)


def evaluate_chromatin_frontier_scenarios(
    evaluation: ChromatinFrontierEvaluationReport | None = None,
) -> ChromatinFrontierScenarioReport:
    selected = evaluation or evaluate_chromatin_frontier_fixture()
    scenarios = default_chromatin_frontier_scenarios()
    receipt_map = {item.record_id: item for item in selected.receipts}
    checks: list[ChromatinFrontierScenarioCheck] = []
    for scenario in scenarios:
        receipt = receipt_map[scenario.record_id]
        passed = receipt.adapter_state == scenario.expected_state and set(
            scenario.expected_issue_codes
        ) <= set(receipt.observed_issue_codes)
        body = {
            "scenario_id": scenario.scenario_id,
            "passed": passed,
            "observed_state": receipt.adapter_state,
            "observed_issue_codes": receipt.observed_issue_codes,
            "detail": "scenario state and issue floor match",
        }
        checks.append(ChromatinFrontierScenarioCheck(**body, content_address=content_hash(body)))
    body = {"fixture_id": selected.fixture_id, "scenarios": scenarios, "checks": checks}
    return ChromatinFrontierScenarioReport(
        selected.fixture_id,
        scenarios,
        tuple(checks),
        content_hash(body),
    )


__all__ = [
    "ChromatinFrontierScenario",
    "ChromatinFrontierScenarioCheck",
    "ChromatinFrontierScenarioReport",
    "default_chromatin_frontier_scenarios",
    "evaluate_chromatin_frontier_scenarios",
]
