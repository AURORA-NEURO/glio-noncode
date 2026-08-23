"""Blocking quality gate across data, evaluation, schema, and reconciliation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignQualityReport:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def run_validation_design_quality_gate(audit: Any, evaluation: Any, adapters: Any, schema: Any, reconciliation: Any) -> ValidationDesignQualityReport:
    checks = ({"check_id": "public-data", "passed": audit.accepted}, {"check_id": "fixture-evaluation", "passed": evaluation.accepted}, {"check_id": "adapter-count", "passed": len(adapters.adapters) == 4}, {"check_id": "schema-version", "passed": schema.version == "validation-design-schema-v1"}, {"check_id": "reconciliation", "passed": reconciliation.accepted}, {"check_id": "checks-closed", "passed": evaluation.failed_checks == 0})
    body = {"checks": checks, "accepted": all(item["passed"] for item in checks)}
    return ValidationDesignQualityReport(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignQualityReport", "run_validation_design_quality_gate"]
