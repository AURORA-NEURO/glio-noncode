"""Public access manifest and prohibited-input boundary."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignAccessManifest:
    boundary: str
    sources: tuple[dict[str, Any], ...]
    prohibited_inputs: tuple[str, ...]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_access_manifest(fixture: Any) -> ValidationDesignAccessManifest:
    sources = tuple({"source_id": source.source_id, "uri": source.uri, "scope": source.scope, "access": "public receipt"} for source in fixture.sources)
    body = {"boundary": fixture.evidence_boundary, "sources": sources, "prohibited_inputs": ("individual-level records", "private credentials", "unreviewed clinical conclusions")}
    return ValidationDesignAccessManifest(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignAccessManifest", "build_validation_design_access_manifest"]
