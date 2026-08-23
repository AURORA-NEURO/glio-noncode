"""Inventory of reproducible release artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseArtifactInventory:
    artifacts: tuple[dict[str, Any], ...]
    complete: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_artifact_inventory(fixture: Any, release: Any) -> EvidenceReleaseArtifactInventory:
    artifacts = (("fixture", fixture.content_address), ("release", release.content_address), ("source-receipts", tuple(item.content_address for item in fixture.sources)))
    rows = tuple({"artifact_type": kind, "content_address": address, "required": True} for kind, address in artifacts)
    def closed(value: Any) -> bool:
        if isinstance(value, (tuple, list)):
            return bool(value) and all(str(item).startswith("sha256:") for item in value)
        return str(value).startswith("sha256:")
    body = {"artifacts": rows, "complete": all(closed(item["content_address"]) for item in rows)}
    return EvidenceReleaseArtifactInventory(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseArtifactInventory", "build_evidence_release_artifact_inventory"]
