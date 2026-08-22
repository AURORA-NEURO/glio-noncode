"""Independent release gate over pipeline artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_pipeline import LinkGraphFoundationFrontierPipelineReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReleaseGateReport:
    checks: tuple[dict[str, Any], ...]
    publishable: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking_failures(self) -> tuple[str, ...]:
        return tuple(item["gate_id"] for item in self.checks if item["blocking"] and not item["passed"])

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": self.checks, "blocking_failures": self.blocking_failures, "publishable": self.publishable}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_foundation_frontier_release_gate(pipeline: LinkGraphFoundationFrontierPipelineReport) -> LinkGraphFoundationFrontierReleaseGateReport:
    checks = tuple({"gate_id": gate_id, "passed": passed, "blocking": True, "detail": detail} for gate_id, passed, detail in (("fixture", pipeline.data.accepted, "fixture audit"), ("replay", pipeline.replay.accepted, "replay"), ("quality", pipeline.quality.accepted, "quality"), ("boundary", pipeline.accessibility.accepted, "boundary"), ("artifacts", pipeline.artifacts.accepted, "artifacts")))
    return LinkGraphFoundationFrontierReleaseGateReport(checks, all(item["passed"] for item in checks))


__all__ = ["LinkGraphFoundationFrontierReleaseGateReport", "evaluate_link_graph_foundation_frontier_release_gate"]
