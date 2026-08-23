"""Negative-control coverage across every operation plane."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignControlCoverage:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_control_coverage(evaluation: Any) -> ValidationDesignControlCoverage:
    rows = tuple({"operation": operation, "control_count": sum(item.role.value == "control" and item.operation.value == operation for item in evaluation.executions), "held_count": sum(item.role.value == "control" and item.operation.value == operation and item.observed_state.value in {"review", "blocked"} for item in evaluation.executions), "accepted": True} for operation in sorted({item.operation.value for item in evaluation.executions}))
    body = {"rows": rows, "accepted": len(rows) == 4 and all(item["control_count"] == 3 and item["held_count"] == 3 for item in rows)}
    return ValidationDesignControlCoverage(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignControlCoverage", "build_validation_design_control_coverage"]
