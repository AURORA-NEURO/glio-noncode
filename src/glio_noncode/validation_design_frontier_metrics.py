"""Operational counts for planning outcomes and control reasons."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable
from .validation_design_frontier_common import issue_counts, operation_counts, state_counts

@dataclass(frozen=True, slots=True)
class ValidationDesignMetrics:
    row_count: int
    check_count: int
    passed_checks: int
    failed_checks: int
    state_counts: dict[str, int]
    operation_counts: dict[str, int]
    issue_counts: dict[str, int]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def measure_validation_design(evaluation: Any) -> ValidationDesignMetrics:
    body = {"row_count": len(evaluation.executions), "check_count": len(evaluation.checks), "passed_checks": evaluation.passed_checks, "failed_checks": evaluation.failed_checks, "state_counts": state_counts(evaluation), "operation_counts": operation_counts(evaluation), "issue_counts": issue_counts(evaluation)}
    return ValidationDesignMetrics(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignMetrics", "measure_validation_design"]
