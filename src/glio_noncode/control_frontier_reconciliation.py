"""Expected-versus-observed reconciliation for control frontier rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierReconciliation:
    fixture_id: str
    items: tuple[ControlFrontierReconciliationItem, ...]
    reconciled: bool
    failed_record_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_control_frontier(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation) -> ControlFrontierReconciliation:
    by_id = {item.record_id: item for item in evaluation.executions}
    items = []
    for record in fixture.records:
        observed = by_id[record.record_id]
        body = {"record_id": record.record_id, "expected_state": record.expected_state.value, "observed_state": observed.state.value, "expected_issue_codes": record.expected_issue_codes, "observed_issue_codes": observed.issue_codes, "passed": observed.state is record.expected_state and observed.issue_codes == record.expected_issue_codes}
        items.append(ControlFrontierReconciliationItem(**body, content_address=content_hash(body)))
    failed = tuple(item.record_id for item in items if not item.passed)
    return ControlFrontierReconciliation(fixture.fixture_id, tuple(items), not failed, failed, content_hash(tuple(items)))


__all__ = ["ControlFrontierReconciliation", "ControlFrontierReconciliationItem", "reconcile_control_frontier"]
