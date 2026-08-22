"""Artifact inventory for beta frontier release outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_bundle import LinkGraphBetaFrontierBundle
from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierArtifact:
    artifact_id: str
    media_type: str
    row_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierArtifactInventory:
    bundle_address: str
    artifacts: tuple[LinkGraphBetaFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def artifact(self, artifact_id: str) -> LinkGraphBetaFrontierArtifact:
        return next(item for item in self.artifacts if item.artifact_id == artifact_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_address": self.bundle_address, "artifacts": [item.to_dict() for item in self.artifacts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_artifacts(bundle: LinkGraphBetaFrontierBundle, evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierArtifactInventory:
    artifacts = (LinkGraphBetaFrontierArtifact("fixture", "application/json", bundle.release.record_count, bundle.release.evaluation_address), LinkGraphBetaFrontierArtifact("metrics", "application/json", len(bundle.metrics.operations), bundle.metrics.content_address), LinkGraphBetaFrontierArtifact("lineage", "application/json", len(bundle.lineage.edges), bundle.lineage.content_address), LinkGraphBetaFrontierArtifact("replay", "application/json", len(evaluation.rows), evaluation.content_address))
    return LinkGraphBetaFrontierArtifactInventory(bundle.content_address, artifacts, bundle.accepted and all(item.content_address.startswith("sha256:") for item in artifacts))


__all__ = ["LinkGraphBetaFrontierArtifact", "LinkGraphBetaFrontierArtifactInventory", "build_link_graph_beta_frontier_artifacts"]
