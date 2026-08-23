"""Depth audit for four capabilities, sixteen rows, and five checks per row."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignDepthAudit:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def audit_validation_design_depth(fixture: Any, evaluation: Any) -> ValidationDesignDepthAudit:
    checks = ({"check_id": "row-count", "passed": len(fixture.records) == 16, "observed": len(fixture.records), "required": 16}, {"check_id": "operation-count", "passed": len({row.operation for row in fixture.records}) == 4, "observed": len({row.operation for row in fixture.records}), "required": 4}, {"check_id": "check-count", "passed": len(evaluation.checks) == 80, "observed": len(evaluation.checks), "required": 80}, {"check_id": "source-count", "passed": len(fixture.sources) == 5, "observed": len(fixture.sources), "required": 5}, {"check_id": "role-count", "passed": (len(fixture.positive_records), len(fixture.control_records)) == (4, 12), "observed": (len(fixture.positive_records), len(fixture.control_records)), "required": (4, 12)}, {"check_id": "accepted", "passed": evaluation.accepted, "observed": evaluation.accepted, "required": True})
    body = {"checks": checks, "accepted": all(item["passed"] for item in checks)}
    return ValidationDesignDepthAudit(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignDepthAudit", "audit_validation_design_depth"]
