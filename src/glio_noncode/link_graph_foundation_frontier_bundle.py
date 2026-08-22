"""Release bundle members for the C01-C04 plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_metrics import LinkGraphFoundationFrontierMetrics
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture
from .link_graph_foundation_frontier_release import LinkGraphFoundationFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierBundleMember:
    member_id: str
    kind: str
    content_address: str
    required: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierBundle:
    bundle_id: str
    release_address: str
    members: tuple[LinkGraphFoundationFrontierBundleMember, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "release_address": self.release_address, "members": [item.to_dict() for item in self.members], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_bundle(fixture: LinkGraphFoundationFrontierFixture, release: LinkGraphFoundationFrontierReleaseManifest, metrics: LinkGraphFoundationFrontierMetrics, lineage: Any) -> LinkGraphFoundationFrontierBundle:
    members = (LinkGraphFoundationFrontierBundleMember("fixture", "fixture", fixture.content_address, True), LinkGraphFoundationFrontierBundleMember("release", "manifest", release.content_address, True), LinkGraphFoundationFrontierBundleMember("metrics", "metrics", metrics.content_address, True), LinkGraphFoundationFrontierBundleMember("lineage", "lineage", lineage.content_address, True))
    return LinkGraphFoundationFrontierBundle("link-graph-foundation-frontier-bundle", release.content_address, members, release.publishable and all(item.content_address.startswith("sha256:") for item in members))


__all__ = ["LinkGraphFoundationFrontierBundle", "LinkGraphFoundationFrontierBundleMember", "build_link_graph_foundation_frontier_bundle"]
