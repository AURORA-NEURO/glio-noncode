"""Deterministic local resource budget for the frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleasePerformanceBudget:
    record_count: int
    max_records: int
    estimated_memory_units: int
    max_memory_units: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_performance_budget(evaluation: ValidationReleaseEvaluation, max_records: int = 1000, max_memory_units: int = 50000) -> ValidationReleasePerformanceBudget:
    records = len(evaluation.executions)
    memory = sum(len(str(item.output)) for item in evaluation.executions)
    body = {"record_count": records, "max_records": max_records, "estimated_memory_units": memory, "max_memory_units": max_memory_units, "accepted": records <= max_records and memory <= max_memory_units}
    return ValidationReleasePerformanceBudget(**body, content_address=content_hash(body))


__all__ = ["ValidationReleasePerformanceBudget", "build_validation_release_performance_budget"]
