"""Explicit release gate that reports every publishability decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReleaseGateCheck:
    gate_id: str
    category: str
    passed: bool
    blocking: bool
    observed: Any
    requirement: str
    action: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReleaseGateReport:
    release_id: str
    checks: tuple[TopologyAlphaFrontierReleaseGateCheck, ...]
    blocking_failures: tuple[str, ...]
    advisory_failures: tuple[str, ...]
    publishable: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def failed(self) -> tuple[TopologyAlphaFrontierReleaseGateCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def by_category(self, category: str) -> tuple[TopologyAlphaFrontierReleaseGateCheck, ...]:
        return tuple(item for item in self.checks if item.category == category)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"release_id": self.release_id, "checks": [item.to_dict() for item in self.checks], "blocking_failures": self.blocking_failures, "advisory_failures": self.advisory_failures, "publishable": self.publishable}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_alpha_frontier_release_gate(pipeline: TopologyAlphaFrontierPipelineReport) -> TopologyAlphaFrontierReleaseGateReport:
    checks = (
        TopologyAlphaFrontierReleaseGateCheck("pipeline", "execution", pipeline.accepted, True, pipeline.accepted, "all twelve pipeline stages pass", "retain the run for review"),
        TopologyAlphaFrontierReleaseGateCheck("evaluation", "replay", pipeline.evaluation.accepted, True, pipeline.evaluation.state_match_count, "states and issue floors match", "repair the failing record"),
        TopologyAlphaFrontierReleaseGateCheck("scope", "boundary", pipeline.boundary.accepted, True, pipeline.fixture.boundary, "aggregate scope is explicit", "block publication"),
        TopologyAlphaFrontierReleaseGateCheck("release", "release", pipeline.release.publishable, True, pipeline.release.publishable, "release manifest is publishable", "keep package in review"),
        TopologyAlphaFrontierReleaseGateCheck("artifacts", "packaging", pipeline.artifacts.accepted, True, len(pipeline.artifacts.artifacts), "all sanitized artifacts are addressed", "rebuild artifact inventory"),
        TopologyAlphaFrontierReleaseGateCheck("review", "advisory", pipeline.review_queue.accepted, False, pipeline.review_queue.count, "control queue is visible", "resolve or retain review records"),
        TopologyAlphaFrontierReleaseGateCheck("trace", "advisory", pipeline.trace.accepted, False, len(pipeline.trace.events), "replay trace is complete", "retain observability receipt"),
    )
    blocking = tuple(item.gate_id for item in checks if item.blocking and not item.passed)
    advisory = tuple(item.gate_id for item in checks if not item.blocking and not item.passed)
    return TopologyAlphaFrontierReleaseGateReport(pipeline.release.release_id, checks, blocking, advisory, not blocking)


__all__ = ["TopologyAlphaFrontierReleaseGateCheck", "TopologyAlphaFrontierReleaseGateReport", "evaluate_topology_alpha_frontier_release_gate"]
