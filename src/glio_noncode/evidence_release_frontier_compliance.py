"""Compliance checks for aggregate-only boundary and claim wording."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseComplianceReport:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_evidence_release_compliance(fixture: Any) -> EvidenceReleaseComplianceReport:
    checks = ({"check_id": "aggregate-boundary", "passed": fixture.evidence_boundary == "public_aggregate_evidence_lifecycle_release"}, {"check_id": "source-receipts", "passed": all(item.uri.startswith("https://") for item in fixture.sources)}, {"check_id": "no-sensitive-field", "passed": all("password" not in str(item.payload).lower() for item in fixture.records)})
    body = {"checks": checks, "accepted": all(item["passed"] for item in checks)}
    return EvidenceReleaseComplianceReport(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseComplianceReport", "evaluate_evidence_release_compliance"]
