"""Expected-versus-observed state reconciliation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseReconciliation:
    matched_records: tuple[str, ...]
    mismatched_records: tuple[str, ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def reconcile_workbench_release(fixture: Any, evaluation: Any) -> WorkbenchReleaseReconciliation:
    expected = {record.record_id: record.expected_state for record in fixture.records}
    matched = tuple(sorted(row.record_id for row in evaluation.executions if expected.get(row.record_id) == row.observed_state))
    mismatched = tuple(sorted(set(expected) - set(matched)))
    body = {"matched_records": matched, "mismatched_records": mismatched, "accepted": not mismatched}
    return WorkbenchReleaseReconciliation(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseReconciliation", "reconcile_workbench_release"]
