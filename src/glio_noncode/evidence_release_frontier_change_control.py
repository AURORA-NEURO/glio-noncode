"""Change-control receipt for fixture, schema, and policy changes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseChangeControl:
    change_id: str
    affected_planes: tuple[str, ...]
    requires_replay: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_change_control(change_id: str, affected_planes: tuple[str, ...]) -> EvidenceReleaseChangeControl:
    body = {"change_id": change_id, "affected_planes": affected_planes, "requires_replay": True}
    return EvidenceReleaseChangeControl(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseChangeControl", "build_evidence_release_change_control"]
