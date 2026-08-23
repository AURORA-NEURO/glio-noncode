"""Five-plane validation matrix for every workbench row."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseValidationMatrix:
    cells: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_workbench_release_validation_matrix(evaluation: Any) -> WorkbenchReleaseValidationMatrix:
    planes = ("state", "issue", "role", "integrity", "safety")
    cells = tuple({"record_id": row.record_id, "plane": plane, "passed": next((check.passed for check in evaluation.checks if check.record_id == row.record_id and check.plane == plane), False)} for row in evaluation.executions for plane in planes)
    body = {"cells": cells, "accepted": all(item["passed"] for item in cells)}
    return WorkbenchReleaseValidationMatrix(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseValidationMatrix", "build_workbench_release_validation_matrix"]
