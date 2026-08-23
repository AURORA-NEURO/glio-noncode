"""Stable human-readable stage transcript."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseTranscript:
    lines: tuple[str, ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_transcript(stage_ids: tuple[str, ...]) -> EvidenceReleaseTranscript:
    lines = tuple(f"{index:02d} completed {stage_id}" for index, stage_id in enumerate(stage_ids, start=1))
    body = {"lines": lines, "accepted": len(lines) == len(stage_ids)}
    return EvidenceReleaseTranscript(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseTranscript", "build_evidence_release_transcript"]
