"""Cross-check release artifact inventory against pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierArtifactCheck:
    artifact_id: str
    kind: str
    address: str
    passed: bool
    required: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierArtifactCheckReport:
    checks: tuple[TopologyAlphaFrontierArtifactCheck, ...]
    required_count: int
    checked_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def required(self) -> tuple[TopologyAlphaFrontierArtifactCheck, ...]:
        return tuple(item for item in self.checks if item.required)

    def failed(self) -> tuple[TopologyAlphaFrontierArtifactCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "required_count": self.required_count, "checked_count": self.checked_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_alpha_frontier_artifacts(pipeline: TopologyAlphaFrontierPipelineReport) -> TopologyAlphaFrontierArtifactCheckReport:
    checks = tuple(TopologyAlphaFrontierArtifactCheck(item.artifact_id, item.kind, item.content_address, item.content_address.startswith("sha256:"), item.release_required, "artifact is content addressed and sanitized") for item in pipeline.artifacts.artifacts)
    return TopologyAlphaFrontierArtifactCheckReport(checks, sum(item.required for item in checks), len(checks), pipeline.artifacts.accepted and all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierArtifactCheck", "TopologyAlphaFrontierArtifactCheckReport", "audit_topology_alpha_frontier_artifacts"]
