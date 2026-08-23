"""Validation matrix with explicit operation and check ownership."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .serialization import content_hash, jsonable


CHECK_PLANES = ("state", "issue", "role", "integrity", "safety")


@dataclass(frozen=True, slots=True)
class PlanningValidationMatrix:
    rows: tuple[dict[str, Any], ...]
    plane_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_validation_matrix(fixture: PlanningFixture, evaluation: PlanningEvaluation) -> PlanningValidationMatrix:
    rows = []
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        row_checks = tuple(item for item in evaluation.checks if item.record_id == record.record_id)
        rows.append({
            "record_id": record.record_id,
            "operation": record.operation.value,
            "role": record.role.value,
            "check_ids": tuple(item.check_id for item in row_checks),
            "planes": tuple(item.plane for item in row_checks),
            "passed": all(item.passed for item in row_checks),
            "execution_address": execution.content_address,
        })
    plane_counts = {plane: sum(item.plane == plane for row in rows for item in evaluation.checks if item.record_id == row["record_id"]) for plane in CHECK_PLANES}
    accepted = len(rows) == len(fixture.records) and all(set(row["planes"]) == set(CHECK_PLANES) and row["passed"] for row in rows)
    body = {"rows": tuple(rows), "plane_counts": plane_counts, "accepted": accepted}
    return PlanningValidationMatrix(tuple(rows), plane_counts, accepted, content_hash(body, prefix="planning-validation-matrix"))


__all__ = ["CHECK_PLANES", "PlanningValidationMatrix", "build_planning_validation_matrix"]
