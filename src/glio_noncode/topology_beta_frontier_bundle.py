"""Content-addressed bundle members for reproducible release assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_delta_depth import TopologyBetaFrontierDeltaDepthReport
from .topology_beta_frontier_metrics import TopologyBetaFrontierMetrics
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture
from .topology_beta_frontier_release import TopologyBetaFrontierReleaseManifest


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierBundleMember:
    member_id: str
    kind: str
    content_address: str
    media_type: str
    required: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierBundle:
    bundle_id: str
    fixture_id: str
    release_id: str
    members: tuple[TopologyBetaFrontierBundleMember, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def member(self, member_id: str) -> TopologyBetaFrontierBundleMember:
        for item in self.members:
            if item.member_id == member_id:
                return item
        raise KeyError(member_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "fixture_id": self.fixture_id, "release_id": self.release_id, "members": [item.to_dict() for item in self.members], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_bundle(fixture: TopologyBetaFrontierFixture, release: TopologyBetaFrontierReleaseManifest, metrics: TopologyBetaFrontierMetrics, deltas: TopologyBetaFrontierDeltaDepthReport) -> TopologyBetaFrontierBundle:
    members = (
        TopologyBetaFrontierBundleMember("fixture", "fixture", fixture.content_address, "application/json", True, "closed public aggregate fixture"),
        TopologyBetaFrontierBundleMember("release", "release_manifest", release.content_address, "application/json", True, "release decision and limitations"),
        TopologyBetaFrontierBundleMember("metrics", "metrics", metrics.content_address, "application/json", True, "stable evaluation metrics"),
        TopologyBetaFrontierBundleMember("deltas", "delta_summary", deltas.content_address, "application/json", True, "positive-control state deltas"),
    )
    return TopologyBetaFrontierBundle("topology-beta-frontier-bundle", fixture.fixture_id, release.release_id, members, all(item.content_address.startswith("sha256:") for item in members) and release.publishable)


__all__ = ["TopologyBetaFrontierBundle", "TopologyBetaFrontierBundleMember", "build_topology_beta_frontier_bundle"]
