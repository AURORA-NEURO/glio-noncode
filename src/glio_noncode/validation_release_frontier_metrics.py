"""Descriptive metrics for the validation-release fixture."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseMetrics:
    record_count: int
    positive_count: int
    control_count: int
    passed_checks: int
    check_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    operation_counts: dict[str, int]
    content_address: str

    @property
    def acceptance_rate(self) -> float:
        return round(self.passed_checks / max(1, self.check_count), 6)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_validation_release(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseMetrics:
    states = Counter(item.observed_state.value for item in evaluation.executions)
    issues = Counter(code for item in evaluation.executions for code in item.issue_codes)
    operations = Counter(item.operation.value for item in evaluation.executions)
    body = {"record_count": len(evaluation.executions), "positive_count": sum(item.role.value == "positive" for item in evaluation.executions), "control_count": sum(item.role.value == "control" for item in evaluation.executions), "passed_checks": evaluation.passed_checks, "check_count": len(evaluation.checks), "state_counts": dict(sorted(states.items())), "issue_counts": dict(sorted(issues.items())), "operation_counts": dict(sorted(operations.items()))}
    return ValidationReleaseMetrics(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseMetrics", "measure_validation_release"]
