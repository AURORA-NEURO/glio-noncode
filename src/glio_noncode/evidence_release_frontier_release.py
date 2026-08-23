"""Release manifest that separates signed receipts from scientific claims."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseManifest:
    release_id: str
    fixture_id: str
    accepted: bool
    record_addresses: tuple[str, ...]
    claim_boundary: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_manifest(fixture: Any, evaluation: Any, quality: Any, lineage: Any, replay: Any, *, release_id: str) -> EvidenceReleaseManifest:
    accepted = bool(quality.accepted and lineage.closed and replay.deterministic and evaluation.accepted)
    body = {"release_id": release_id, "fixture_id": fixture.fixture_id, "accepted": accepted, "record_addresses": tuple(item.content_address for item in evaluation.executions), "claim_boundary": "research lifecycle receipt; not clinical or causal evidence"}
    return EvidenceReleaseManifest(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseManifest", "build_evidence_release_manifest"]
