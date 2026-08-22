"""Evidence bundle assembly for topology context release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_delta_depth import TopologyContextFrontierDeltaDepthReport
from .topology_context_frontier_metrics import TopologyContextFrontierMetrics
from .topology_context_frontier_public_data import TopologyContextFrontierFixture
from .topology_context_frontier_release import TopologyContextFrontierReleaseManifest


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierBundleMember:
    member_id: str
    kind: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierBundle:
    bundle_id: str
    members: tuple[TopologyContextFrontierBundleMember, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "bundle_id": self.bundle_id,
            "members": [item.to_dict() for item in self.members],
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_bundle(
    fixture: TopologyContextFrontierFixture,
    release: TopologyContextFrontierReleaseManifest,
    metrics: TopologyContextFrontierMetrics,
    deltas: TopologyContextFrontierDeltaDepthReport,
) -> TopologyContextFrontierBundle:
    members = (
        TopologyContextFrontierBundleMember("fixture", "fixture", fixture.content_address),
        TopologyContextFrontierBundleMember("release", "release", release.content_address),
        TopologyContextFrontierBundleMember("metrics", "metrics", metrics.content_address),
        TopologyContextFrontierBundleMember("deltas", "delta_depth", deltas.content_address),
    )
    return TopologyContextFrontierBundle(
        "topology-context-frontier-bundle", members, release.publishable and deltas.accepted
    )


__all__ = [
    "TopologyContextFrontierBundle",
    "TopologyContextFrontierBundleMember",
    "build_topology_context_frontier_bundle",
]
