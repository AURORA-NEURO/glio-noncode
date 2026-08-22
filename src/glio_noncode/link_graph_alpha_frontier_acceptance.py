"""Acceptance report joining release, controls, and review requirements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierAcceptanceReport:
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_alpha_frontier_acceptance(pipeline: LinkGraphAlphaFrontierPipelineReport) -> LinkGraphAlphaFrontierAcceptanceReport:
    checks = (check("pipeline", pipeline.accepted, "all pipeline stages pass"), check("release", pipeline.release.publishable, "release manifest is publishable"), check("bundle", pipeline.bundle.accepted, "bundle members are closed"), check("artifacts", pipeline.artifacts.accepted, "artifact inventory is complete"), check("review", len(pipeline.review_queue.entries) == len(pipeline.evaluation.rows), "review queue covers every result"))
    return LinkGraphAlphaFrontierAcceptanceReport(checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierAcceptanceReport", "evaluate_link_graph_alpha_frontier_acceptance"]
