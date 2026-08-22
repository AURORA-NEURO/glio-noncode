"""Composite report for the deepest inspectable link-plane surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_assurance import LinkGraphAlphaFrontierAssuranceReport
from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport
from .link_graph_alpha_frontier_review_actions import LinkGraphAlphaFrontierReviewActionPlan
from .link_graph_alpha_frontier_scenario_runner import LinkGraphAlphaFrontierScenarioRunReport
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierCompositeReport:
    pipeline_address: str
    assurance_address: str
    actions_address: str
    scenarios_address: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"pipeline_address": self.pipeline_address, "assurance_address": self.assurance_address, "actions_address": self.actions_address, "scenarios_address": self.scenarios_address, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_composite(pipeline: LinkGraphAlphaFrontierPipelineReport, assurance: LinkGraphAlphaFrontierAssuranceReport, actions: LinkGraphAlphaFrontierReviewActionPlan, scenarios: LinkGraphAlphaFrontierScenarioRunReport) -> LinkGraphAlphaFrontierCompositeReport:
    addresses = (pipeline.content_address, assurance.content_address, actions.content_address, scenarios.content_address)
    return LinkGraphAlphaFrontierCompositeReport(*addresses, all(item.startswith("sha256:") for item in addresses) and pipeline.accepted and assurance.accepted and actions.accepted and scenarios.accepted)


__all__ = ["LinkGraphAlphaFrontierCompositeReport", "build_link_graph_alpha_frontier_composite"]
