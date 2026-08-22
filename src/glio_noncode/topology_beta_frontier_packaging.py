"""Release package manifest with explicit file roles and checksums."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_pipeline import TopologyBetaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierPackageFile:
    path: str
    role: str
    media_type: str
    content_address: str
    required: bool
    sanitized: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierPackageManifest:
    package_id: str
    version: str
    scope: str
    files: tuple[TopologyBetaFrontierPackageFile, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def required_files(self) -> tuple[TopologyBetaFrontierPackageFile, ...]:
        return tuple(item for item in self.files if item.required)

    def by_role(self, role: str) -> tuple[TopologyBetaFrontierPackageFile, ...]:
        return tuple(item for item in self.files if item.role == role)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"package_id": self.package_id, "version": self.version, "scope": self.scope, "files": [item.to_dict() for item in self.files], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_package_manifest(pipeline: TopologyBetaFrontierPipelineReport) -> TopologyBetaFrontierPackageManifest:
    files = (
        TopologyBetaFrontierPackageFile("fixture.json", "fixture", "application/json", pipeline.fixture.content_address, True, True, "closed public aggregate fixture"),
        TopologyBetaFrontierPackageFile("evaluation.json", "evaluation", "application/json", pipeline.evaluation.content_address, True, True, "state and issue replay"),
        TopologyBetaFrontierPackageFile("metrics.json", "metrics", "application/json", pipeline.metrics.content_address, True, True, "stable evaluation metrics"),
        TopologyBetaFrontierPackageFile("review.csv", "review", "text/csv", pipeline.view.content_address, True, True, "review table with controls"),
        TopologyBetaFrontierPackageFile("release.json", "release", "application/json", pipeline.release.content_address, True, True, "release limitations"),
        TopologyBetaFrontierPackageFile("artifacts.json", "artifacts", "application/json", pipeline.artifacts.content_address, True, True, "artifact inventory"),
        TopologyBetaFrontierPackageFile("trace.json", "trace", "application/json", pipeline.trace.content_address, False, True, "observability trace"),
        TopologyBetaFrontierPackageFile("pipeline.json", "pipeline", "application/json", pipeline.content_address, True, True, "twelve-stage pipeline report"),
    )
    return TopologyBetaFrontierPackageManifest("topology-beta-frontier-package", pipeline.fixture.version, pipeline.fixture.boundary, files, pipeline.accepted and all(item.sanitized and item.content_address.startswith("sha256:") for item in files))


__all__ = ["TopologyBetaFrontierPackageFile", "TopologyBetaFrontierPackageManifest", "build_topology_beta_frontier_package_manifest"]
