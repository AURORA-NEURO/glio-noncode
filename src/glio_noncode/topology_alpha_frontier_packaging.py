"""Release package manifest with explicit file roles and content addresses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierPackageFile:
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
class TopologyAlphaFrontierPackageManifest:
    package_id: str
    version: str
    scope: str
    files: tuple[TopologyAlphaFrontierPackageFile, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def required_files(self) -> tuple[TopologyAlphaFrontierPackageFile, ...]:
        return tuple(item for item in self.files if item.required)

    def by_role(self, role: str) -> tuple[TopologyAlphaFrontierPackageFile, ...]:
        return tuple(item for item in self.files if item.role == role)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"package_id": self.package_id, "version": self.version, "scope": self.scope, "files": [item.to_dict() for item in self.files], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_package_manifest(pipeline: TopologyAlphaFrontierPipelineReport) -> TopologyAlphaFrontierPackageManifest:
    files = (
        TopologyAlphaFrontierPackageFile("fixture.json", "fixture", "application/json", pipeline.fixture.content_address, True, True, "closed public aggregate fixture"),
        TopologyAlphaFrontierPackageFile("evaluation.json", "evaluation", "application/json", pipeline.evaluation.content_address, True, True, "state and issue replay"),
        TopologyAlphaFrontierPackageFile("metrics.json", "metrics", "application/json", pipeline.metrics.content_address, True, True, "stable operation metrics"),
        TopologyAlphaFrontierPackageFile("review.csv", "review", "text/csv", pipeline.view.content_address, True, True, "review table with controls"),
        TopologyAlphaFrontierPackageFile("release.json", "release", "application/json", pipeline.release.content_address, True, True, "release limitations"),
        TopologyAlphaFrontierPackageFile("artifacts.json", "artifacts", "application/json", pipeline.artifacts.content_address, True, True, "artifact inventory"),
        TopologyAlphaFrontierPackageFile("trace.json", "trace", "application/json", pipeline.trace.content_address, False, True, "structured replay trace"),
        TopologyAlphaFrontierPackageFile("pipeline.json", "pipeline", "application/json", pipeline.content_address, True, True, "twelve-stage pipeline report"),
    )
    accepted = pipeline.accepted and all(item.sanitized and item.content_address.startswith("sha256:") for item in files)
    return TopologyAlphaFrontierPackageManifest("topology-alpha-frontier-package", pipeline.fixture.version, pipeline.fixture.boundary, files, accepted)


__all__ = ["TopologyAlphaFrontierPackageFile", "TopologyAlphaFrontierPackageManifest", "build_topology_alpha_frontier_package_manifest"]
