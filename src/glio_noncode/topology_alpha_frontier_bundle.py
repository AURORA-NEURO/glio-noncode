"""Content-addressed bundle members for alpha release assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_delta_depth import TopologyAlphaFrontierDeltaDepthReport
from .topology_alpha_frontier_metrics import TopologyAlphaFrontierMetrics
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture
from .topology_alpha_frontier_release import TopologyAlphaFrontierReleaseManifest


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierBundleMember:
    member_id: str
    kind: str
    content_address: str
    media_type: str
    required: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierBundle:
    bundle_id: str
    fixture_id: str
    release_id: str
    members: tuple[TopologyAlphaFrontierBundleMember, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def member(self, member_id: str) -> TopologyAlphaFrontierBundleMember:
        for item in self.members:
            if item.member_id == member_id:
                return item
        raise KeyError(member_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "fixture_id": self.fixture_id, "release_id": self.release_id, "members": [item.to_dict() for item in self.members], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_bundle(fixture: TopologyAlphaFrontierFixture, release: TopologyAlphaFrontierReleaseManifest, metrics: TopologyAlphaFrontierMetrics, deltas: TopologyAlphaFrontierDeltaDepthReport) -> TopologyAlphaFrontierBundle:
    members = (TopologyAlphaFrontierBundleMember("fixture", "fixture", fixture.content_address, "application/json", True, "closed aggregate fixture"), TopologyAlphaFrontierBundleMember("release", "release_manifest", release.content_address, "application/json", True, "release decision and limitations"), TopologyAlphaFrontierBundleMember("metrics", "metrics", metrics.content_address, "application/json", True, "stable evaluation metrics"), TopologyAlphaFrontierBundleMember("deltas", "delta_summary", deltas.content_address, "application/json", True, "positive-control state deltas"))
    return TopologyAlphaFrontierBundle("topology-alpha-frontier-bundle", fixture.fixture_id, release.release_id, members, release.publishable and all(item.content_address.startswith("sha256:") for item in members))


__all__ = ["TopologyAlphaFrontierBundle", "TopologyAlphaFrontierBundleMember", "build_topology_alpha_frontier_bundle"]
