"""Public source access manifest."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseAccessManifest:
    boundary: str
    sources: tuple[dict[str, Any], ...]
    prohibited_inputs: tuple[str, ...]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_workbench_release_access_manifest(fixture: Any) -> WorkbenchReleaseAccessManifest:
    sources = tuple({"source_id": source.source_id, "uri": source.uri, "scope": source.scope, "access": "public receipt"} for source in fixture.sources)
    body = {"boundary": fixture.evidence_boundary, "sources": sources, "prohibited_inputs": ("individual-level records", "private credentials", "unreviewed clinical conclusions")}
    return WorkbenchReleaseAccessManifest(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseAccessManifest", "build_workbench_release_access_manifest"]
