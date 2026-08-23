"""Citation graph receipt for source-to-capability coverage."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseCitationGraph:
    edges: tuple[dict[str, Any], ...]
    source_count: int
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_citation_graph(fixture: Any) -> EvidenceReleaseCitationGraph:
    edges = tuple({"source_id": source_id, "record_id": record.record_id, "capability": record.capability} for record in fixture.records for source_id in record.source_ids)
    body = {"edges": edges, "source_count": len(fixture.sources), "closed": all(edge["source_id"] in {source.source_id for source in fixture.sources} for edge in edges)}
    return EvidenceReleaseCitationGraph(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseCitationGraph", "build_evidence_release_citation_graph"]
