"""Release manifest for the aggregate topology-alpha package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture
from .topology_alpha_frontier_quality_gate import TopologyAlphaFrontierQualityReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    version: str
    scope: str
    publishable: bool
    artifact_ids: tuple[str, ...]
    required_review_count: int
    limitations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"release_id": self.release_id, "fixture_id": self.fixture_id, "version": self.version, "scope": self.scope, "publishable": self.publishable, "artifact_ids": self.artifact_ids, "required_review_count": self.required_review_count, "limitations": self.limitations}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_release(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation, quality: TopologyAlphaFrontierQualityReport) -> TopologyAlphaFrontierReleaseManifest:
    artifacts = tuple(f"artifact-{row.record_id}" for row in evaluation.rows) + ("artifact-fixture", "artifact-sources", "artifact-metrics", "artifact-review")
    return TopologyAlphaFrontierReleaseManifest("topology-alpha-frontier-release", fixture.fixture_id, fixture.version, fixture.boundary, bool(evaluation.accepted and quality.accepted), artifacts, sum(row.role == "control" for row in evaluation.rows), ("Aggregate public data only.", "Orientation, channel, state, and edge simulation outputs remain descriptive.", "External calibration and transport evaluation remain separate.", "No clinical conclusion is produced."))


__all__ = ["TopologyAlphaFrontierReleaseManifest", "build_topology_alpha_frontier_release"]
