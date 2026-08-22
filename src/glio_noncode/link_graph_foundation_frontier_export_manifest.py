"""Export manifest for machine-readable C01-C04 review bundles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_field_projection import project_link_graph_foundation_frontier_evaluation, project_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierExportArtifact:
    artifact_id: str
    media_type: str
    row_count: int
    schema_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierExportManifest:
    fixture_id: str
    format_version: str
    boundary: str
    artifacts: tuple[LinkGraphFoundationFrontierExportArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def artifact(self, artifact_id: str) -> LinkGraphFoundationFrontierExportArtifact:
        return next(item for item in self.artifacts if item.artifact_id == artifact_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "format_version": self.format_version, "boundary": self.boundary, "artifacts": [item.to_dict() for item in self.artifacts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_export_manifest(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierExportManifest:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_foundation_frontier_fixture_eval", fromlist=["evaluate_link_graph_foundation_frontier_fixture"]).evaluate_link_graph_foundation_frontier_fixture(value)
    fixture_projection = project_link_graph_foundation_frontier_fixture(value)
    evaluation_projection = project_link_graph_foundation_frontier_evaluation(replay)
    artifacts = (LinkGraphFoundationFrontierExportArtifact("fixture-records", "application/json", len(fixture_projection.rows), fixture_projection.schema.content_address, content_hash(fixture_projection.rows)), LinkGraphFoundationFrontierExportArtifact("replay-results", "application/json", len(evaluation_projection), fixture_projection.schema.content_address, content_hash(evaluation_projection)))
    return LinkGraphFoundationFrontierExportManifest(value.fixture_id, "2026.08.export.v1", value.boundary, artifacts, bool(artifacts) and replay.accepted)


def export_link_graph_foundation_frontier_manifest(manifest: LinkGraphFoundationFrontierExportManifest) -> dict[str, Any]:
    return manifest.to_dict()


__all__ = ["LinkGraphFoundationFrontierExportArtifact", "LinkGraphFoundationFrontierExportManifest", "build_link_graph_foundation_frontier_export_manifest", "export_link_graph_foundation_frontier_manifest"]
