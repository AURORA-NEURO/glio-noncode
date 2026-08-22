"""Bounded release manifest for the C05-C08 beta link baseline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LINK_GRAPH_BETA_FRONTIER_FIXTURE_VERSION, LinkGraphBetaFrontierFixture
from .link_graph_beta_frontier_quality_gate import LinkGraphBetaFrontierQualityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    fixture_version: str
    record_count: int
    source_count: int
    operation_count: int
    quality_address: str
    evaluation_address: str
    limitations: tuple[str, ...]
    publishable: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"release_id": self.release_id, "fixture_id": self.fixture_id, "fixture_version": self.fixture_version, "record_count": self.record_count, "source_count": self.source_count, "operation_count": self.operation_count, "quality_address": self.quality_address, "evaluation_address": self.evaluation_address, "limitations": self.limitations, "publishable": self.publishable}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_release(fixture: LinkGraphBetaFrontierFixture, evaluation: LinkGraphBetaFrontierEvaluation, quality: LinkGraphBetaFrontierQualityReport, *, release_id: str = "link-graph-beta-frontier-release") -> LinkGraphBetaFrontierReleaseManifest:
    limitations = ("activity and contact remain descriptive components", "coaccessibility is a candidate evidence method", "q-value transforms are bounded support summaries", "allele direction conflict is retained", "aggregate evidence is not a clinical or causal conclusion")
    return LinkGraphBetaFrontierReleaseManifest(release_id, fixture.fixture_id, fixture.version, len(fixture.records), len(fixture.sources), 4, quality.content_address, evaluation.content_address, limitations, quality.accepted and evaluation.accepted and fixture.version == LINK_GRAPH_BETA_FRONTIER_FIXTURE_VERSION)


__all__ = ["LinkGraphBetaFrontierReleaseManifest", "build_link_graph_beta_frontier_release"]
