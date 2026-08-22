"""Human-oriented validation report assembled from the alpha pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierValidationSection:
    section_id: str
    title: str
    passed: bool
    observed_count: int
    expected_count: int
    detail: str
    evidence_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierValidationReport:
    report_id: str
    run_id: str
    sections: tuple[TopologyAlphaFrontierValidationSection, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def section(self, section_id: str) -> TopologyAlphaFrontierValidationSection:
        for item in self.sections:
            if item.section_id == section_id:
                return item
        raise KeyError(section_id)

    def failed(self) -> tuple[TopologyAlphaFrontierValidationSection, ...]:
        return tuple(item for item in self.sections if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"report_id": self.report_id, "run_id": self.run_id, "sections": [item.to_dict() for item in self.sections], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_validation_report(pipeline: TopologyAlphaFrontierPipelineReport) -> TopologyAlphaFrontierValidationReport:
    sections = (
        TopologyAlphaFrontierValidationSection("fixture", "Fixture balance", pipeline.data.accepted, pipeline.data.record_count, 16, "four operation groups have one positive and three controls", pipeline.fixture.content_address),
        TopologyAlphaFrontierValidationSection("replay", "Primitive replay", pipeline.evaluation.accepted, pipeline.evaluation.state_match_count, 16, "expected states and issue floors match", pipeline.evaluation.content_address),
        TopologyAlphaFrontierValidationSection("quality", "Quality gate", pipeline.quality.accepted, len(pipeline.quality.checks), len(pipeline.quality.checks), "quality checks are complete", pipeline.quality.content_address),
        TopologyAlphaFrontierValidationSection("review", "Review visibility", pipeline.review_queue.accepted, pipeline.review_queue.count, 12, "controls retain open dispositions", pipeline.review_queue.content_address),
        TopologyAlphaFrontierValidationSection("release", "Release bundle", pipeline.release.publishable and pipeline.bundle.accepted and pipeline.artifacts.accepted, len(pipeline.artifacts.artifacts), 20, "bundle and artifact inventory are publishable", pipeline.release.content_address),
        TopologyAlphaFrontierValidationSection("trace", "Observability", pipeline.trace.accepted, len(pipeline.trace.events), 16, "one trace event is retained per evaluation row", pipeline.trace.content_address),
    )
    return TopologyAlphaFrontierValidationReport("topology-alpha-frontier-validation", pipeline.run_id, sections, all(item.passed for item in sections))


__all__ = ["TopologyAlphaFrontierValidationReport", "TopologyAlphaFrontierValidationSection", "build_topology_alpha_frontier_validation_report"]
