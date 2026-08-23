"""Run-level manifest for platform runtime reproducibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PLATFORM_FRONTIER_BOUNDARY, PLATFORM_FRONTIER_VERSION
from .platform_frontier_provenance import PlatformFrontierProvenanceReceipt
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierRunManifest:
    run_id: str
    fixture_version: str
    boundary: str
    provenance_address: str
    command: str
    stage_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_run_manifest(run_id: str, provenance: PlatformFrontierProvenanceReceipt, stage_ids: tuple[str, ...], *, command: str = "platform-frontier-pipeline") -> PlatformFrontierRunManifest:
    body = {"run_id": run_id, "fixture_version": PLATFORM_FRONTIER_VERSION, "boundary": PLATFORM_FRONTIER_BOUNDARY, "provenance_address": provenance.content_address, "command": command, "stage_ids": stage_ids, "accepted": provenance.complete and len(stage_ids) == 24}
    return PlatformFrontierRunManifest(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierRunManifest", "build_platform_frontier_run_manifest"]
