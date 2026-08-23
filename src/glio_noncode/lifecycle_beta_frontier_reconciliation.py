"""Expected-versus-observed reconciliation for C05-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReconciliationItem:
    record_id: str
    state_match: bool
    issue_match: bool
    role_match: bool
    reconciled: bool
    observed_state: str
    expected_state: str
    observed_issues: tuple[str, ...]
    expected_issues: tuple[str, ...]
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReconciliationReport:
    fixture_id: str
    items: tuple[LifecycleBetaFrontierReconciliationItem, ...]
    reconciled: bool
    failed_record_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_lifecycle_beta_frontier(fixture: LifecycleBetaFrontierFixture, evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierReconciliationReport:
    records = {item.record_id: item for item in fixture.records}
    items = []
    for execution in evaluation.executions:
        record = records[execution.record_id]
        state_match = execution.state is record.expected_state
        issue_match = execution.issue_codes == record.expected_issue_codes
        role_match = execution.accepted is (record.role.value == "positive")
        body = {"record_id": record.record_id, "state_match": state_match, "issue_match": issue_match, "role_match": role_match, "reconciled": state_match and issue_match and role_match, "observed_state": execution.state.value, "expected_state": record.expected_state.value, "observed_issues": execution.issue_codes, "expected_issues": record.expected_issue_codes, "detail": record.notes}
        items.append(LifecycleBetaFrontierReconciliationItem(**body, content_address=content_hash(body)))
    failed = tuple(item.record_id for item in items if not item.reconciled)
    return LifecycleBetaFrontierReconciliationReport(fixture.fixture_id, tuple(items), not failed, failed, content_hash({"items": tuple(items), "failed": failed}))


__all__ = ["LifecycleBetaFrontierReconciliationItem", "LifecycleBetaFrontierReconciliationReport", "reconcile_lifecycle_beta_frontier"]
