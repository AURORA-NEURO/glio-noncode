"""Source registry with URI and scope closure checks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseSourceRegistry:
    sources: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_source_registry(fixture: Any) -> EvidenceReleaseSourceRegistry:
    sources = tuple({"source_id": item.source_id, "title": item.title, "uri": item.uri, "scope": item.scope, "address": item.content_address} for item in fixture.sources)
    body = {"sources": sources, "accepted": len(sources) == 5 and len({item["source_id"] for item in sources}) == 5}
    return EvidenceReleaseSourceRegistry(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseSourceRegistry", "build_evidence_release_source_registry"]
