"""Invariant assertions for deployment frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierFixture
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierInvariant:
    invariant_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierInvariantReport:
    invariants: tuple[DeploymentFrontierInvariant, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_deployment_frontier_invariants(fixture: DeploymentFrontierFixture, evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierInvariantReport:
    values = (("record-count", len(fixture.records) == 16, "sixteen fixture records"), ("execution-count", len(evaluation.executions) == len(fixture.records), "one execution per record"), ("check-count", len(evaluation.checks) == 80, "five checks per record"), ("positive-count", len(fixture.positive_records) == 4, "one positive per operation"), ("control-count", len(fixture.control_records) == 12, "three controls per operation"), ("state-boundary", all(item.role.value == "positive" or item.issue_codes for item in evaluation.executions), "control outputs carry issues"))
    rows = []
    for invariant_id, passed, detail in values:
        body = {"invariant_id": invariant_id, "passed": passed, "detail": detail}
        rows.append(DeploymentFrontierInvariant(**body, content_address=deployment_address(body)))
    return DeploymentFrontierInvariantReport(tuple(rows), all(item.passed for item in rows), deployment_address(tuple(rows)))


def assert_deployment_frontier_invariants(report: DeploymentFrontierInvariantReport) -> None:
    if not report.accepted:
        raise AssertionError(tuple(item.invariant_id for item in report.invariants if not item.passed))


__all__ = ["DeploymentFrontierInvariant", "DeploymentFrontierInvariantReport", "assert_deployment_frontier_invariants", "evaluate_deployment_frontier_invariants"]
