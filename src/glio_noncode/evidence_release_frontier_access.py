"""Public access manifest for aggregate fixtures and derived receipts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseAccessManifest:
    boundary: str
    public_sources: tuple[dict[str, Any], ...]
    prohibited_inputs: tuple[str, ...]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_access_manifest(fixture: Any) -> EvidenceReleaseAccessManifest:
    sources = tuple({"source_id": item.source_id, "uri": item.uri, "scope": item.scope, "access": "public receipt"} for item in fixture.sources)
    body = {"boundary": fixture.evidence_boundary, "public_sources": sources, "prohibited_inputs": ("individual-level records", "private credentials", "unreviewed clinical conclusions")}
    return EvidenceReleaseAccessManifest(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseAccessManifest", "build_evidence_release_access_manifest"]
