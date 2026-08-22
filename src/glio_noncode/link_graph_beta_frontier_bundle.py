"""Release bundle joining fixture, manifest, metrics, and lineage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_lineage import LinkGraphBetaFrontierLineage
from .link_graph_beta_frontier_metrics import LinkGraphBetaFrontierMetrics
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture
from .link_graph_beta_frontier_release import LinkGraphBetaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierBundle:
    fixture_id: str
    release: LinkGraphBetaFrontierReleaseManifest
    metrics: LinkGraphBetaFrontierMetrics
    lineage: LinkGraphBetaFrontierLineage
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "release": self.release.to_dict(), "metrics": self.metrics.to_dict(), "lineage": self.lineage.to_dict(), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_bundle(fixture: LinkGraphBetaFrontierFixture, release: LinkGraphBetaFrontierReleaseManifest, metrics: LinkGraphBetaFrontierMetrics, lineage: LinkGraphBetaFrontierLineage) -> LinkGraphBetaFrontierBundle:
    return LinkGraphBetaFrontierBundle(fixture.fixture_id, release, metrics, lineage, release.publishable and metrics.accepted and lineage.accepted)


__all__ = ["LinkGraphBetaFrontierBundle", "build_link_graph_beta_frontier_bundle"]
