"""Reproducibility packet joining fixture, evaluation, replay, and lineage."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseReproducibilityPacket:
    fixture_address: str
    evaluation_address: str
    replay_address: str
    lineage_address: str
    complete: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_reproducibility_packet(fixture: Any, evaluation: Any, replay: Any, lineage: Any) -> EvidenceReleaseReproducibilityPacket:
    body = {"fixture_address": fixture.content_address, "evaluation_address": evaluation.content_address, "replay_address": replay.content_address, "lineage_address": lineage.content_address, "complete": replay.deterministic and lineage.closed}
    return EvidenceReleaseReproducibilityPacket(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseReproducibilityPacket", "build_evidence_release_reproducibility_packet"]
