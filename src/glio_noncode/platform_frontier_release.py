"""Bounded release manifest for the platform-control frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PLATFORM_FRONTIER_BOUNDARY, PLATFORM_FRONTIER_VERSION, PlatformFrontierEvaluation, PlatformFrontierFixture
from .platform_frontier_lineage import PlatformFrontierLineage
from .platform_frontier_quality_gate import PlatformFrontierQualityReport
from .platform_frontier_replay import PlatformFrontierReplayReport
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class PlatformFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    fixture_version: str
    boundary: str
    evaluation_address: str
    quality_address: str
    lineage_address: str
    replay_address: str
    accepted: bool
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.release_id, "release_id")
        if self.boundary != PLATFORM_FRONTIER_BOUNDARY:
            raise ValueError("platform release boundary must remain aggregate")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_release(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation, quality: PlatformFrontierQualityReport, lineage: PlatformFrontierLineage, replay: PlatformFrontierReplayReport, *, release_id: str = "platform-frontier-release") -> PlatformFrontierReleaseManifest:
    limitations = ("aggregate operational fixture", "no private row-level data", "no scientific or clinical conclusion")
    body = {"release_id": release_id, "fixture_id": fixture.fixture_id, "fixture_version": PLATFORM_FRONTIER_VERSION, "boundary": PLATFORM_FRONTIER_BOUNDARY, "evaluation_address": evaluation.content_address, "quality_address": quality.content_address, "lineage_address": lineage.content_address, "replay_address": replay.content_address, "accepted": quality.accepted and replay.accepted and evaluation.accepted, "limitations": limitations}
    return PlatformFrontierReleaseManifest(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierReleaseManifest", "build_platform_frontier_release"]
