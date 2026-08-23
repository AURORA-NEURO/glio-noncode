"""Package manifest joining artifact classes and release identity."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleasePackageManifest:
    package_id: str
    artifact_types: tuple[str, ...]
    complete: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_package_manifest(release: Any, artifacts: Any) -> EvidenceReleasePackageManifest:
    types = tuple(item["artifact_type"] for item in artifacts.artifacts)
    body = {"package_id": release.release_id, "artifact_types": types, "complete": artifacts.complete and release.accepted}
    return EvidenceReleasePackageManifest(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleasePackageManifest", "build_evidence_release_package_manifest"]
