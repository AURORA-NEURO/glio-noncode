"""Research-only release manifest for control frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import CONTROL_FRONTIER_BOUNDARY, CONTROL_FRONTIER_VERSION, ControlFrontierEvaluation, ControlFrontierFixture
from .control_frontier_lineage import ControlFrontierLineage
from .control_frontier_quality_gate import ControlFrontierQualityReport
from .control_frontier_replay import ControlFrontierReplayReport
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ControlFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    version: str
    boundary: str
    research_only: bool
    quality_accepted: bool
    replay_deterministic: bool
    lineage_accepted: bool
    artifact_addresses: dict[str, str]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.release_id, "release_id")
        if not self.research_only:
            raise ValueError("control frontier releases are research-only")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_release(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation, quality: ControlFrontierQualityReport, lineage: ControlFrontierLineage, replay: ControlFrontierReplayReport, *, release_id: str = "control-frontier-release") -> ControlFrontierReleaseManifest:
    body = {"release_id": release_id, "fixture_id": fixture.fixture_id, "version": CONTROL_FRONTIER_VERSION, "boundary": CONTROL_FRONTIER_BOUNDARY, "research_only": True, "quality_accepted": quality.accepted, "replay_deterministic": replay.deterministic, "lineage_accepted": lineage.accepted, "artifact_addresses": {"fixture": fixture.content_address, "evaluation": evaluation.content_address, "quality": quality.content_address, "lineage": lineage.content_address, "replay": replay.content_address}, "allowed_uses": ("research-use-only", "aggregate-operational-review", "reproducibility-testing"), "excluded_uses": ("clinical-decision", "patient-ranking", "autonomous-action")}
    accepted = bool(quality.accepted and replay.deterministic and lineage.accepted and body["boundary"] == CONTROL_FRONTIER_BOUNDARY)
    return ControlFrontierReleaseManifest(**body, accepted=accepted, content_address=content_hash({**body, "accepted": accepted}))


__all__ = ["ControlFrontierReleaseManifest", "build_control_frontier_release"]
