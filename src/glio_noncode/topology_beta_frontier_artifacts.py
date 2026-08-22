"""Artifact inventory for the topology-beta release bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_bundle import TopologyBetaFrontierBundle
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierArtifact:
    artifact_id: str
    kind: str
    record_id: str | None
    media_type: str
    content_address: str
    release_required: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierArtifactInventory:
    artifacts: tuple[TopologyBetaFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_kind(self, kind: str) -> tuple[TopologyBetaFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind == kind)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"artifacts": [item.to_dict() for item in self.artifacts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_artifacts(bundle: TopologyBetaFrontierBundle, evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierArtifactInventory:
    artifacts = [TopologyBetaFrontierArtifact(item.member_id, item.kind, None, item.media_type, item.content_address, item.required, item.detail) for item in bundle.members]
    artifacts.extend(TopologyBetaFrontierArtifact(f"artifact-{row.record_id}", "record_result", row.record_id, "application/json", row.adapter.content_address, False, f"replayed {row.operation} result") for row in evaluation.rows)
    values = tuple(artifacts)
    return TopologyBetaFrontierArtifactInventory(values, len(values) == 20 and all(item.content_address.startswith("sha256:") for item in values))


__all__ = ["TopologyBetaFrontierArtifact", "TopologyBetaFrontierArtifactInventory", "build_topology_beta_frontier_artifacts"]
