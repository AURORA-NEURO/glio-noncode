"""Counts and issue metrics for editing-design evaluation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable
from .editing_design_frontier_common import issue_counts, operation_counts, state_counts

@dataclass(frozen=True, slots=True)
class EditingDesignMetrics:
    row_count: int
    check_count: int
    passed_checks: int
    failed_checks: int
    state_counts: dict[str, int]
    operation_counts: dict[str, int]
    issue_counts: dict[str, int]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def measure_editing_design(evaluation: Any) -> EditingDesignMetrics:
    body = {"row_count": len(evaluation.executions), "check_count": len(evaluation.checks), "passed_checks": evaluation.passed_checks, "failed_checks": evaluation.failed_checks, "state_counts": state_counts(evaluation), "operation_counts": operation_counts(evaluation), "issue_counts": issue_counts(evaluation)}; return EditingDesignMetrics(**body, content_address=content_hash(body))

__all__ = ["EditingDesignMetrics", "measure_editing_design"]
