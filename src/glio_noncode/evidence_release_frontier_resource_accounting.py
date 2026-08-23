"""Output-resource accounting for rows, checks, and public receipts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseResourceReport:
    rows: int
    checks: int
    sources: int
    bounded: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def account_evidence_release_resources(evaluation: Any) -> EvidenceReleaseResourceReport:
    body = {"rows": len(evaluation.executions), "checks": len(evaluation.checks), "sources": 5}
    return EvidenceReleaseResourceReport(**body, bounded=body["rows"] <= 1000 and body["checks"] <= 10000, content_address=content_hash(body | {"bounded": body["rows"] <= 1000 and body["checks"] <= 10000}))

__all__ = ["EvidenceReleaseResourceReport", "account_evidence_release_resources"]
