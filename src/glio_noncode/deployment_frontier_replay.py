"""Deterministic replay receipts for the deployment frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierFixture
from .deployment_frontier_fixture_eval import evaluate_deployment_frontier_fixture
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReplayCheck:
    check_id: str
    passed: bool
    first_address: str
    second_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReplayReport:
    checks: tuple[DeploymentFrontierReplayCheck, ...]
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_deployment_frontier_evaluation(fixture: DeploymentFrontierFixture, evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierReplayReport:
    second = evaluate_deployment_frontier_fixture(fixture)
    checks = []
    for check_id, first_address, second_address in (
        ("evaluation-address", evaluation.content_address, second.content_address),
        ("check-addresses", deployment_address(evaluation.checks), deployment_address(second.checks)),
        ("execution-addresses", deployment_address(evaluation.executions), deployment_address(second.executions)),
    ):
        body = {"check_id": check_id, "passed": first_address == second_address, "first_address": first_address, "second_address": second_address}
        checks.append(DeploymentFrontierReplayCheck(**body, content_address=deployment_address(body)))
    return DeploymentFrontierReplayReport(tuple(checks), all(item.passed for item in checks), deployment_address(tuple(checks)))


def replay_is_deterministic(report: DeploymentFrontierReplayReport) -> bool:
    return report.deterministic


__all__ = ["DeploymentFrontierReplayCheck", "DeploymentFrontierReplayReport", "replay_deployment_frontier_evaluation", "replay_is_deterministic"]
