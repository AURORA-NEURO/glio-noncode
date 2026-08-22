"""Artifact inventory for reproducible release and review handoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_bundle import LinkGraphAlphaFrontierBundle
from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierArtifact:
    artifact_id: str
    artifact_kind: str
    content_address: str
    record_count: int
    media_type: str
    retention: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierArtifactInventory:
    artifacts: tuple[LinkGraphAlphaFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_kind(self, artifact_kind: str) -> tuple[LinkGraphAlphaFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.artifact_kind == artifact_kind)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"artifacts": [item.to_dict() for item in self.artifacts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_artifacts(bundle: LinkGraphAlphaFrontierBundle, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierArtifactInventory:
    artifacts = (
        LinkGraphAlphaFrontierArtifact("replay-json", "replay", evaluation.content_address, len(evaluation.rows), "application/json", "release"),
        LinkGraphAlphaFrontierArtifact("review-table", "review", content_hash({"bundle": bundle.content_address, "rows": evaluation.rows}), len(evaluation.rows), "text/csv", "release"),
        LinkGraphAlphaFrontierArtifact("bundle-manifest", "manifest", bundle.content_address, len(bundle.members), "application/json", "release"),
        LinkGraphAlphaFrontierArtifact("control-report", "controls", content_hash(tuple(row.record_id for row in evaluation.controls())), len(evaluation.controls()), "application/json", "release"),
    )
    return LinkGraphAlphaFrontierArtifactInventory(artifacts, bundle.accepted and all(item.content_address.startswith("sha256:") for item in artifacts))


__all__ = ["LinkGraphAlphaFrontierArtifact", "LinkGraphAlphaFrontierArtifactInventory", "build_link_graph_alpha_frontier_artifacts"]
