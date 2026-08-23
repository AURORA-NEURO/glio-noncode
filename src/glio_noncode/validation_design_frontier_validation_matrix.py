"""Five validation planes for every planning row."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignValidationMatrix:
    cells: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_validation_matrix(evaluation: Any) -> ValidationDesignValidationMatrix:
    planes = ("state", "issue", "role", "integrity", "safety")
    cells = tuple({"record_id": row.record_id, "plane": plane, "passed": next((check.passed for check in evaluation.checks if check.record_id == row.record_id and check.plane == plane), False)} for row in evaluation.executions for plane in planes)
    body = {"cells": cells, "accepted": len(cells) == 80 and all(item["passed"] for item in cells)}
    return ValidationDesignValidationMatrix(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignValidationMatrix", "build_validation_design_validation_matrix"]
