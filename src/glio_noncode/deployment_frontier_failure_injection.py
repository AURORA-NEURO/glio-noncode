"""Failure probes for the four deployment control boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierOperation, DeploymentFrontierState
from .deployment_frontier_operations import run_deployment_frontier_operation
from .deployment_frontier_public_data import default_deployment_frontier_fixture
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierFailureInjection:
    probe_id: str
    operation: DeploymentFrontierOperation
    injected_issue: str
    observed_state: DeploymentFrontierState
    blocked: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierFailureReport:
    probes: tuple[DeploymentFrontierFailureInjection, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_deployment_frontier_failure_injections() -> DeploymentFrontierFailureReport:
    fixture = default_deployment_frontier_fixture()
    controls = tuple(item for item in fixture.control_records)
    probes = []
    for index, record in enumerate(controls, start=1):
        result = run_deployment_frontier_operation(record.operation, record.payload)
        body = {"probe_id": f"failure-probe-{index:02d}", "operation": record.operation, "injected_issue": record.expected_issue_codes[0], "observed_state": result.state, "blocked": bool(result.issue_codes)}
        probes.append(DeploymentFrontierFailureInjection(**body, content_address=deployment_address(body)))
    return DeploymentFrontierFailureReport(tuple(probes), len(probes) == 12 and all(item.blocked for item in probes), deployment_address(tuple(probes)))


__all__ = ["DeploymentFrontierFailureInjection", "DeploymentFrontierFailureReport", "run_deployment_frontier_failure_injections"]
