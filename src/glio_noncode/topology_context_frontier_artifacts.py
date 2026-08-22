"""Artifact inventory for the topology evidence bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_bundle import TopologyContextFrontierBundle
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierArtifact:
    artifact_id: str
    kind: str
    content_address: str
    byte_count: int
    sanitized: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierArtifactInventory:
    artifacts: tuple[TopologyContextFrontierArtifact, ...]
    accepted: bool
    total_bytes: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "artifacts": [item.to_dict() for item in self.artifacts],
            "accepted": self.accepted,
            "total_bytes": self.total_bytes,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_artifacts(
    bundle: TopologyContextFrontierBundle,
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierArtifactInventory:
    artifacts = tuple(
        TopologyContextFrontierArtifact(
            item.member_id, item.kind, item.content_address, len(item.content_address), True
        )
        for item in bundle.members
    ) + tuple(
        TopologyContextFrontierArtifact(
            f"result-{item.record_id}",
            "result",
            item.adapter.content_address,
            len(item.adapter.content_address),
            True,
        )
        for item in evaluation.rows
    )
    return TopologyContextFrontierArtifactInventory(
        artifacts,
        all(item.sanitized for item in artifacts),
        sum(item.byte_count for item in artifacts),
    )


__all__ = [
    "TopologyContextFrontierArtifact",
    "TopologyContextFrontierArtifactInventory",
    "build_topology_context_frontier_artifacts",
]
