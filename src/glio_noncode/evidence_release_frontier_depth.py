"""Depth audit across evidence, controls, verification, and release planes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseDepthAudit:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def audit_evidence_release_depth(fixture: Any, evaluation: Any) -> EvidenceReleaseDepthAudit:
    checks = (
        {"check_id": "row-count", "passed": len(fixture.records) == 16, "observed": len(fixture.records), "required": 16},
        {"check_id": "operation-count", "passed": len(fixture.operation_names) == 4, "observed": fixture.operation_names, "required": 4},
        {"check_id": "check-count", "passed": len(evaluation.checks) == 81, "observed": len(evaluation.checks), "required": 81},
        {"check_id": "positive-controls", "passed": len(fixture.positive_records) == 4 and len(fixture.control_records) == 12, "observed": (len(fixture.positive_records), len(fixture.control_records)), "required": (4, 12)},
        {"check_id": "public-receipts", "passed": len(fixture.sources) == 5, "observed": len(fixture.sources), "required": 5},
        {"check_id": "evaluation", "passed": evaluation.accepted, "observed": evaluation.accepted, "required": True},
    )
    body = {"checks": checks, "accepted": all(item["passed"] for item in checks)}
    return EvidenceReleaseDepthAudit(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseDepthAudit", "audit_evidence_release_depth"]
