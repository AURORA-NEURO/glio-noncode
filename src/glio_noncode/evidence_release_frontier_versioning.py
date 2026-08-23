"""Schema version compatibility helpers."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseVersion:
    release_version: str
    schema_version: str
    compatible: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def current_evidence_release_version() -> EvidenceReleaseVersion:
    body = {"release_version": "2026.08.d14-c13-c16.v1", "schema_version": "evidence-release-schema-v1", "compatible": True}
    return EvidenceReleaseVersion(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseVersion", "current_evidence_release_version"]
