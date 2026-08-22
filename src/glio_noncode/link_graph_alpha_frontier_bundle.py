"""Release bundle membership and content-addressed package closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_metrics import LinkGraphAlphaFrontierMetrics
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_release import LinkGraphAlphaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierBundleMember:
    member_id: str
    kind: str
    content_address: str
    required: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierBundle:
    bundle_id: str
    release_address: str
    members: tuple[LinkGraphAlphaFrontierBundleMember, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def member(self, member_id: str) -> LinkGraphAlphaFrontierBundleMember:
        for item in self.members:
            if item.member_id == member_id:
                return item
        raise KeyError(member_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "release_address": self.release_address, "members": [item.to_dict() for item in self.members], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_bundle(fixture: LinkGraphAlphaFrontierFixture, release: LinkGraphAlphaFrontierReleaseManifest, metrics: LinkGraphAlphaFrontierMetrics, deltas: Any) -> LinkGraphAlphaFrontierBundle:
    members = (
        LinkGraphAlphaFrontierBundleMember("fixture", "fixture", fixture.content_address, True, "closed public aggregate fixture"),
        LinkGraphAlphaFrontierBundleMember("release", "manifest", release.content_address, True, "release decision and limitations"),
        LinkGraphAlphaFrontierBundleMember("metrics", "metrics", metrics.content_address, True, "state and control metrics"),
        LinkGraphAlphaFrontierBundleMember("deltas", "comparison", deltas.content_address, True, "positive-control contrasts"),
    )
    accepted = release.publishable and all(item.content_address.startswith("sha256:") for item in members)
    return LinkGraphAlphaFrontierBundle("link-graph-alpha-frontier-bundle", release.content_address, members, accepted)


__all__ = ["LinkGraphAlphaFrontierBundle", "LinkGraphAlphaFrontierBundleMember", "build_link_graph_alpha_frontier_bundle"]
