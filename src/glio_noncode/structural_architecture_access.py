"""Export allow-list and privacy checks for architecture artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .structural_architecture_contracts import StructuralArchitectureArtifact, addressed


@dataclass(frozen=True, slots=True)
class StructuralArchitectureAccessManifest:
    manifest_id: str
    allowed_media_types: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    aggregate_only: bool
    raw_payload_export: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "allowed_media_types": list(self.allowed_media_types),
            "artifact_ids": list(self.artifact_ids),
            "aggregate_only": self.aggregate_only,
            "raw_payload_export": self.raw_payload_export,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def build_structural_architecture_access_manifest(
    artifacts: tuple[StructuralArchitectureArtifact, ...],
) -> StructuralArchitectureAccessManifest:
    media_types = tuple(sorted({item.media_type for item in artifacts}))
    artifact_ids = tuple(item.artifact_id for item in artifacts)
    accepted = (
        bool(artifacts)
        and len(artifact_ids) == len(set(artifact_ids))
        and all(
            item.media_type in {"application/json", "text/csv", "text/markdown"}
            for item in artifacts
        )
    )
    body = {
        "manifest_id": "structural-architecture-access-v1",
        "allowed_media_types": media_types,
        "artifact_ids": artifact_ids,
        "aggregate_only": True,
        "raw_payload_export": False,
        "accepted": accepted,
    }
    return StructuralArchitectureAccessManifest(
        **body, content_address=addressed(body, "structural-access")
    )


__all__ = ["StructuralArchitectureAccessManifest", "build_structural_architecture_access_manifest"]
