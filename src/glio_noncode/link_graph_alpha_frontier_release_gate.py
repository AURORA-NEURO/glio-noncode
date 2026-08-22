"""Explicit release-gate checks kept separate from the pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReleaseGateCheck:
    gate_id: str
    passed: bool
    blocking: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReleaseGateReport:
    checks: tuple[LinkGraphAlphaFrontierReleaseGateCheck, ...]
    publishable: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking_failures(self) -> tuple[str, ...]:
        return tuple(item.gate_id for item in self.checks if item.blocking and not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "blocking_failures": self.blocking_failures, "publishable": self.publishable}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_alpha_frontier_release_gate(pipeline: LinkGraphAlphaFrontierPipelineReport) -> LinkGraphAlphaFrontierReleaseGateReport:
    checks = (
        LinkGraphAlphaFrontierReleaseGateCheck("fixture", pipeline.data.accepted, True, "fixture audit accepted"),
        LinkGraphAlphaFrontierReleaseGateCheck("replay", pipeline.evaluation.accepted, True, "fixture replay accepted"),
        LinkGraphAlphaFrontierReleaseGateCheck("quality", pipeline.quality.accepted, True, "quality gate accepted"),
        LinkGraphAlphaFrontierReleaseGateCheck("boundary", pipeline.boundary.accepted, True, "claim boundary accepted"),
        LinkGraphAlphaFrontierReleaseGateCheck("integrity", pipeline.integrity.accepted, True, "content integrity accepted"),
        LinkGraphAlphaFrontierReleaseGateCheck("artifacts", pipeline.artifacts.accepted, True, "artifact inventory accepted"),
        LinkGraphAlphaFrontierReleaseGateCheck("review", pipeline.review_queue.accepted, False, "review queue is complete"),
    )
    return LinkGraphAlphaFrontierReleaseGateReport(checks, all(item.passed for item in checks if item.blocking))


__all__ = ["LinkGraphAlphaFrontierReleaseGateCheck", "LinkGraphAlphaFrontierReleaseGateReport", "evaluate_link_graph_alpha_frontier_release_gate"]
