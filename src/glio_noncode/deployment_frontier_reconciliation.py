"""Expected/observed reconciliation for positive and control rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierFixture
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issues: tuple[str, ...]
    observed_issues: tuple[str, ...]
    matched: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReconciliation:
    items: tuple[DeploymentFrontierReconciliationItem, ...]
    matched_count: int
    mismatch_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_deployment_frontier(fixture: DeploymentFrontierFixture, evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierReconciliation:
    records = {item.record_id: item for item in fixture.records}
    items = []
    for execution in evaluation.executions:
        record = records[execution.record_id]
        matched = execution.state is record.expected_state and set(record.expected_issue_codes) <= set(execution.issue_codes)
        body = {"record_id": record.record_id, "expected_state": record.expected_state.value, "observed_state": execution.state.value, "expected_issues": record.expected_issue_codes, "observed_issues": execution.issue_codes, "matched": matched}
        items.append(DeploymentFrontierReconciliationItem(**body, content_address=deployment_address(body)))
    mismatch = tuple(item.record_id for item in items if not item.matched)
    body = {"items": tuple(items), "matched_count": len(items) - len(mismatch), "mismatch_ids": mismatch, "accepted": not mismatch}
    return DeploymentFrontierReconciliation(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierReconciliation", "DeploymentFrontierReconciliationItem", "reconcile_deployment_frontier"]
