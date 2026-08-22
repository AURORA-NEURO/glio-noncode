"""Release manifest for the bounded topology context package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_public_data import TopologyContextFrontierFixture
from .topology_context_frontier_quality_gate import TopologyContextFrontierQualityReport


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    version: str
    publishable: bool
    artifact_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "release_id": self.release_id,
            "fixture_id": self.fixture_id,
            "version": self.version,
            "publishable": self.publishable,
            "artifact_ids": self.artifact_ids,
            "limitations": self.limitations,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_release(
    fixture: TopologyContextFrontierFixture,
    evaluation: TopologyContextFrontierEvaluation,
    quality: TopologyContextFrontierQualityReport,
) -> TopologyContextFrontierReleaseManifest:
    return TopologyContextFrontierReleaseManifest(
        "topology-context-frontier-release",
        fixture.fixture_id,
        fixture.version,
        bool(evaluation.accepted and quality.accepted),
        tuple(f"artifact-{item.record_id}" for item in evaluation.rows),
        (
            "No clinical conclusion is produced.",
            "External assay calibration remains separate.",
            "Aggregate fixture only.",
        ),
    )


__all__ = [
    "TopologyContextFrontierReleaseManifest",
    "build_topology_context_frontier_release",
]
