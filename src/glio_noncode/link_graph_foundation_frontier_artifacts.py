"""Artifact inventory for baseline review and release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_bundle import LinkGraphFoundationFrontierBundle
from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierArtifact:
    artifact_id: str
    kind: str
    content_address: str
    record_count: int
    media_type: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierArtifactInventory:
    artifacts: tuple[LinkGraphFoundationFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"artifacts": [item.to_dict() for item in self.artifacts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_artifacts(bundle: LinkGraphFoundationFrontierBundle, evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierArtifactInventory:
    artifacts = (LinkGraphFoundationFrontierArtifact("fixture-replay", "replay", evaluation.content_address, len(evaluation.rows), "application/json"), LinkGraphFoundationFrontierArtifact("review-table", "review", content_hash(evaluation.rows), len(evaluation.rows), "text/csv"), LinkGraphFoundationFrontierArtifact("bundle-manifest", "manifest", bundle.content_address, len(bundle.members), "application/json"))
    return LinkGraphFoundationFrontierArtifactInventory(artifacts, bundle.accepted and all(item.content_address.startswith("sha256:") for item in artifacts))


__all__ = ["LinkGraphFoundationFrontierArtifact", "LinkGraphFoundationFrontierArtifactInventory", "build_link_graph_foundation_frontier_artifacts"]
