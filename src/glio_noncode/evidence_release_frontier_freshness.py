"""Receipt freshness policy without network access or mutable source reads."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseFreshnessReport:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_evidence_release_freshness(fixture: Any) -> EvidenceReleaseFreshnessReport:
    checks = tuple({"source_id": source.source_id, "version_declared": bool(source.version), "uri_declared": bool(source.uri)} for source in fixture.sources)
    body = {"checks": checks, "accepted": all(item["version_declared"] and item["uri_declared"] for item in checks)}
    return EvidenceReleaseFreshnessReport(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseFreshnessReport", "evaluate_evidence_release_freshness"]
