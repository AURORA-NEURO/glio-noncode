"""Content-address and identity checks for the release graph."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseIntegrityReport:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_evidence_release_integrity(fixture: Any, evaluation: Any) -> EvidenceReleaseIntegrityReport:
    checks = ({"check_id": "fixture-address", "passed": fixture.content_address.startswith("sha256:")}, {"check_id": "record-addresses", "passed": all(row.content_address.startswith("sha256:") for row in fixture.records)}, {"check_id": "execution-addresses", "passed": all(row.content_address.startswith("sha256:") for row in evaluation.executions)}, {"check_id": "identity-closure", "passed": len({row.record_id for row in evaluation.executions}) == len(fixture.records)})
    body = {"checks": checks, "accepted": all(item["passed"] for item in checks)}
    return EvidenceReleaseIntegrityReport(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseIntegrityReport", "evaluate_evidence_release_integrity"]
