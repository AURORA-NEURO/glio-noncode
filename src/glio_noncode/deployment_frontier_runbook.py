"""Executable runbook stages for deployment frontier operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierRunbookStep:
    sequence: int
    step_id: str
    command: str
    input_kind: str
    output_kind: str
    failure_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierRunbook:
    steps: tuple[DeploymentFrontierRunbookStep, ...]
    executable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_runbook() -> DeploymentFrontierRunbook:
    rows = (
        ("audit", "audit-deployment-frontier-data", "fixture", "data-audit", "stop-on-failure"),
        ("evaluate", "evaluate-deployment-frontier", "fixture", "evaluation", "route-controls"),
        ("replay", "replay-deployment-frontier", "evaluation", "replay", "compare-addresses"),
        ("release", "release-deployment-frontier", "evidence", "release", "hold-release"),
    )
    steps = []
    for sequence, (step_id, command, input_kind, output_kind, failure_action) in enumerate(rows, start=1):
        body = {"sequence": sequence, "step_id": step_id, "command": command, "input_kind": input_kind, "output_kind": output_kind, "failure_action": failure_action}
        steps.append(DeploymentFrontierRunbookStep(**body, content_address=deployment_address(body)))
    return DeploymentFrontierRunbook(tuple(steps), all(item.command and item.failure_action for item in steps), deployment_address(tuple(steps)))


def runbook_is_executable(runbook: DeploymentFrontierRunbook) -> bool:
    return runbook.executable and tuple(item.sequence for item in runbook.steps) == tuple(range(1, len(runbook.steps) + 1))


__all__ = ["DeploymentFrontierRunbook", "DeploymentFrontierRunbookStep", "build_deployment_frontier_runbook", "runbook_is_executable"]
