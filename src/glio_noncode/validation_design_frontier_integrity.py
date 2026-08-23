"""Content-address and identity closure checks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignIntegrityReport:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_validation_design_integrity(fixture: Any, evaluation: Any) -> ValidationDesignIntegrityReport:
    record_ids = tuple(item.record_id for item in fixture.records)
    execution_ids = tuple(item.record_id for item in evaluation.executions)
    checks = ({"check_id": "fixture-address", "passed": fixture.content_address.startswith("sha256:")}, {"check_id": "execution-addresses", "passed": all(item.content_address.startswith("sha256:") for item in evaluation.executions)}, {"check_id": "record-identity", "passed": record_ids == execution_ids}, {"check_id": "unique-records", "passed": len(record_ids) == len(set(record_ids))}, {"check_id": "source-addresses", "passed": all(item.content_address.startswith("sha256:") for item in fixture.sources)})
    body = {"checks": checks, "accepted": all(item["passed"] for item in checks)}
    return ValidationDesignIntegrityReport(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignIntegrityReport", "evaluate_validation_design_integrity"]
