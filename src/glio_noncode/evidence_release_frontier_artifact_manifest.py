"""Detailed artifact manifest with role-specific file projections."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseArtifactManifest:
    files: tuple[dict[str, Any], ...]
    required_file_count: int
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_artifact_manifest(addresses: Iterable[str]) -> EvidenceReleaseArtifactManifest:
    names = ("fixture.json", "evaluation.json", "review.csv", "release.json", "sources.json", "runtime.json")
    files = tuple({"name": name, "content_address": address} for name, address in zip(names, addresses, strict=False))
    body = {"files": files, "required_file_count": len(names), "complete": len(files) == len(names) and all(item["content_address"].startswith("sha256:") for item in files)}
    return EvidenceReleaseArtifactManifest(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseArtifactManifest", "build_evidence_release_artifact_manifest"]
