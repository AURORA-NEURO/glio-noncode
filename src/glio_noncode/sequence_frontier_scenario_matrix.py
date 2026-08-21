"""Positive and negative scenario matrix for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_fixture_eval import (
    SequenceFrontierEvaluationReport,
    evaluate_sequence_frontier_fixture,
)
from .sequence_frontier_public_data import (
    SequenceFrontierOperation,
    SequenceFrontierRole,
    default_sequence_frontier_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceFrontierScenario:
    scenario_id: str
    operation: SequenceFrontierOperation
    role: SequenceFrontierRole
    record_id: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierScenarioCheck:
    scenario_id: str
    passed: bool
    observed_state: str
    observed_issue_codes: tuple[str, ...]
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierScenarioReport:
    fixture_id: str
    scenarios: tuple[SequenceFrontierScenario, ...]
    checks: tuple[SequenceFrontierScenarioCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.scenarios) and all(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def default_sequence_frontier_scenarios() -> tuple[SequenceFrontierScenario, ...]:
    fixture = default_sequence_frontier_fixture()
    scenarios: list[SequenceFrontierScenario] = []
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
        scenarios.append(SequenceFrontierScenario(**body, content_address=content_hash(body)))
    return tuple(scenarios)


def evaluate_sequence_frontier_scenarios(
    evaluation: SequenceFrontierEvaluationReport | None = None,
) -> SequenceFrontierScenarioReport:
    selected = evaluation or evaluate_sequence_frontier_fixture()
    scenarios = default_sequence_frontier_scenarios()
    receipt_map = {item.record_id: item for item in selected.receipts}
    checks: list[SequenceFrontierScenarioCheck] = []
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
        checks.append(SequenceFrontierScenarioCheck(**body, content_address=content_hash(body)))
    body = {"fixture_id": selected.fixture_id, "scenarios": scenarios, "checks": checks}
    return SequenceFrontierScenarioReport(
        selected.fixture_id, scenarios, tuple(checks), content_hash(body)
    )


__all__ = [
    "SequenceFrontierScenario",
    "SequenceFrontierScenarioCheck",
    "SequenceFrontierScenarioReport",
    "default_sequence_frontier_scenarios",
    "evaluate_sequence_frontier_scenarios",
]
