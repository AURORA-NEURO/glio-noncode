"""Blocking quality gate for the workbench-release surface."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseQualityReport:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def run_workbench_release_quality_gate(audit: Any, evaluation: Any, adapters: Any, schema: Any, reconciliation: Any) -> WorkbenchReleaseQualityReport:
    checks = ({"check_id": "data", "passed": audit.accepted}, {"check_id": "fixture", "passed": evaluation.accepted}, {"check_id": "adapter-count", "passed": len(adapters.adapters) == 4}, {"check_id": "schema", "passed": schema.version == "workbench-release-schema-v1"}, {"check_id": "reconciliation", "passed": reconciliation.accepted})
    body = {"checks": checks, "accepted": all(item["passed"] for item in checks)}
    return WorkbenchReleaseQualityReport(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseQualityReport", "run_workbench_release_quality_gate"]
