"""Validation report assembled from all matrix and boundary checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierValidationReport:
    report_id: str
    passed_checks: int
    total_checks: int
    failed_stages: tuple[str, ...]
    boundary: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"report_id": self.report_id, "passed_checks": self.passed_checks, "total_checks": self.total_checks, "failed_stages": self.failed_stages, "boundary": self.boundary, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_validation_report(pipeline: LinkGraphAlphaFrontierPipelineReport) -> LinkGraphAlphaFrontierValidationReport:
    reports = (pipeline.quality.checks, pipeline.invariants.results, pipeline.boundary.checks, pipeline.accessibility.checks, pipeline.schema.checks)
    total = sum(len(items) for items in reports)
    passed = sum(sum(item.passed for item in items) for items in reports)
    return LinkGraphAlphaFrontierValidationReport("link-graph-alpha-frontier-validation", passed, total, pipeline.failed_stages, pipeline.boundary.boundary, pipeline.accepted and passed == total)


__all__ = ["LinkGraphAlphaFrontierValidationReport", "build_link_graph_alpha_frontier_validation_report"]
