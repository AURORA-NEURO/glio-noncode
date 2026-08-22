"""Positive and control scenario checks for Domain 09 topology evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_frontier_fixture_eval import TopologyFrontierEvaluationReport
from .topology_frontier_public_data import (
    TopologyFrontierFixture,
    TopologyFrontierRole,
    default_topology_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class TopologyFrontierScenario:
    record_id: str
    operation: str
    role: TopologyFrontierRole
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierScenarioCheck:
    check_id: str
    record_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierScenarioReport:
    fixture_id: str
    scenarios: tuple[TopologyFrontierScenario, ...]
    checks: tuple[TopologyFrontierScenarioCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.scenarios) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "failed_check_ids": list(self.failed_check_ids)}


def evaluate_topology_frontier_scenarios(
    evaluation: TopologyFrontierEvaluationReport,
    *,
    fixture: TopologyFrontierFixture | None = None,
) -> TopologyFrontierScenarioReport:
    selected = fixture or default_topology_frontier_fixture()
    records = selected.record_map()
    scenarios: list[TopologyFrontierScenario] = []
    checks: list[TopologyFrontierScenarioCheck] = []

    def add(check_id: str, record_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
        checks.append(TopologyFrontierScenarioCheck(**body, content_address=content_hash(body)))

    for receipt in evaluation.receipts:
        record = records[receipt.record_id]
        expected = set(record.expected_issue_codes)
        observed = set(receipt.observed_issue_codes)
        state_ok = receipt.adapter_state == record.expected_state
        issue_ok = expected <= observed
        role_ok = (
            receipt.adapter_state == "supported"
            if record.role is TopologyFrontierRole.POSITIVE
            else receipt.adapter_state != "supported"
        )
        passed = state_ok and issue_ok and role_ok
        detail = "state, issue floor, and role expectation agree" if passed else "scenario expectation requires review"
        body = {
            "record_id": receipt.record_id,
            "operation": receipt.operation.value,
            "role": receipt.role,
            "expected_state": record.expected_state,
            "observed_state": receipt.adapter_state,
            "expected_issue_codes": record.expected_issue_codes,
            "observed_issue_codes": receipt.observed_issue_codes,
            "passed": passed,
            "detail": detail,
        }
        scenarios.append(TopologyFrontierScenario(**body, content_address=content_hash(body)))
        add(f"{receipt.record_id}:state", receipt.record_id, state_ok, "expected state matches")
        add(f"{receipt.record_id}:issues", receipt.record_id, issue_ok, "expected issue floor is present")
        add(f"{receipt.record_id}:role", receipt.record_id, role_ok, "positive/control role remains visible")
    body = {"fixture_id": selected.fixture_id, "scenarios": scenarios, "checks": checks}
    return TopologyFrontierScenarioReport(selected.fixture_id, tuple(scenarios), tuple(checks), content_hash(body))


__all__ = [
    "TopologyFrontierScenario",
    "TopologyFrontierScenarioCheck",
    "TopologyFrontierScenarioReport",
    "evaluate_topology_frontier_scenarios",
]
