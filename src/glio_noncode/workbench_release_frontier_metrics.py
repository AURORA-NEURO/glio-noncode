"""State, issue, operation, and role metrics for workbench review."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable
from .workbench_release_frontier_common import issue_counts, state_counts

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseMetrics:
    row_count: int
    positive_count: int
    control_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    operation_counts: dict[str, int]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def measure_workbench_release(evaluation: Any) -> WorkbenchReleaseMetrics:
    operations: dict[str, int] = {}
    for row in evaluation.executions:
        operations[row.operation.value] = operations.get(row.operation.value, 0) + 1
    positive = sum(row.role.value == "positive" for row in evaluation.executions)
    body = {"row_count": len(evaluation.executions), "positive_count": positive, "control_count": len(evaluation.executions) - positive, "state_counts": state_counts(evaluation), "issue_counts": issue_counts(evaluation), "operation_counts": dict(sorted(operations.items()))}
    return WorkbenchReleaseMetrics(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseMetrics", "measure_workbench_release"]
