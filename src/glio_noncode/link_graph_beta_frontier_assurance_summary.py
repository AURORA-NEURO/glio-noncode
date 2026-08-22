"""Single summary over beta quality, release, and boundary reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_pipeline import LinkGraphBetaFrontierPipelineReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierAssuranceSummary:
    fixture_id: str
    stage_count: int
    passed_stage_count: int
    record_count: int
    source_count: int
    state_accuracy: float
    quality_accepted: bool
    release_publishable: bool
    artifact_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "stage_count": self.stage_count, "passed_stage_count": self.passed_stage_count, "record_count": self.record_count, "source_count": self.source_count, "state_accuracy": self.state_accuracy, "quality_accepted": self.quality_accepted, "release_publishable": self.release_publishable, "artifact_count": self.artifact_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_assurance_summary(pipeline: LinkGraphBetaFrontierPipelineReport) -> LinkGraphBetaFrontierAssuranceSummary:
    passed = sum(stage.status == "passed" for stage in pipeline.stages)
    accepted = pipeline.accepted and pipeline.quality.accepted and pipeline.release.publishable and pipeline.artifacts.accepted
    return LinkGraphBetaFrontierAssuranceSummary(pipeline.fixture.fixture_id, len(pipeline.stages), passed, len(pipeline.fixture.records), len(pipeline.fixture.sources), pipeline.metrics.state_accuracy, pipeline.quality.accepted, pipeline.release.publishable, len(pipeline.artifacts.artifacts), accepted)


__all__ = ["LinkGraphBetaFrontierAssuranceSummary", "build_link_graph_beta_frontier_assurance_summary"]
