"""Address and state delta between two deployment evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDeltaRow:
    record_id: str
    state_changed: bool
    issue_changed: bool
    before_state: str
    after_state: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDeltaReport:
    rows: tuple[DeploymentFrontierDeltaRow, ...]
    changed_count: int
    identical: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def compare_deployment_frontier_evaluations(before: DeploymentFrontierEvaluation, after: DeploymentFrontierEvaluation) -> DeploymentFrontierDeltaReport:
    left = {item.record_id: item for item in before.executions}
    rows = []
    for item in after.executions:
        prior = left.get(item.record_id)
        body = {"record_id": item.record_id, "state_changed": prior is None or prior.state != item.state, "issue_changed": prior is None or prior.issue_codes != item.issue_codes, "before_state": prior.state.value if prior else "missing", "after_state": item.state.value}
        rows.append(DeploymentFrontierDeltaRow(**body, content_address=deployment_address(body)))
    changed = sum(item.state_changed or item.issue_changed for item in rows)
    return DeploymentFrontierDeltaReport(tuple(rows), changed, changed == 0, deployment_address(tuple(rows)))


__all__ = ["DeploymentFrontierDeltaReport", "DeploymentFrontierDeltaRow", "compare_deployment_frontier_evaluations"]
