"""Export manifest for stable beta frontier review artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_field_projection import project_link_graph_beta_frontier_evaluation, project_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierExportArtifact:
    artifact_id: str
    media_type: str
    row_count: int
    schema_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierExportManifest:
    fixture_id: str
    format_version: str
    boundary: str
    artifacts: tuple[LinkGraphBetaFrontierExportArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def artifact(self, artifact_id: str) -> LinkGraphBetaFrontierExportArtifact:
        return next(item for item in self.artifacts if item.artifact_id == artifact_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "format_version": self.format_version, "boundary": self.boundary, "artifacts": [item.to_dict() for item in self.artifacts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_export_manifest(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierExportManifest:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_beta_frontier_fixture_eval", fromlist=["evaluate_link_graph_beta_frontier_fixture"]).evaluate_link_graph_beta_frontier_fixture(value)
    projection = project_link_graph_beta_frontier_fixture(value)
    results = project_link_graph_beta_frontier_evaluation(replay)
    artifacts = (LinkGraphBetaFrontierExportArtifact("fixture-records", "application/json", len(projection.rows), projection.schema.content_address, content_hash(projection.rows)), LinkGraphBetaFrontierExportArtifact("replay-results", "application/json", len(results), projection.schema.content_address, content_hash(results)))
    return LinkGraphBetaFrontierExportManifest(value.fixture_id, "2026.08.beta-export.v1", value.boundary, artifacts, bool(artifacts) and replay.accepted)


__all__ = ["LinkGraphBetaFrontierExportArtifact", "LinkGraphBetaFrontierExportManifest", "build_link_graph_beta_frontier_export_manifest"]
