"""Boundary accessibility checks for beta frontier exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LINK_GRAPH_BETA_FRONTIER_BOUNDARY, LinkGraphBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierAccessibilityReport:
    fixture_id: str
    boundary: str
    public_aggregate: bool
    context_count: int
    redaction_required: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "boundary": self.boundary, "public_aggregate": self.public_aggregate, "context_count": self.context_count, "redaction_required": self.redaction_required, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_beta_frontier_accessibility(fixture: LinkGraphBetaFrontierFixture, evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierAccessibilityReport:
    contexts = {record.context_key for record in fixture.records}
    accepted = fixture.boundary == LINK_GRAPH_BETA_FRONTIER_BOUNDARY and all(source.public_aggregate for source in fixture.sources) and evaluation.accepted and not any("patient" in str(record.payload).lower() for record in fixture.records)
    return LinkGraphBetaFrontierAccessibilityReport(fixture.fixture_id, fixture.boundary, all(source.public_aggregate for source in fixture.sources), len(contexts), False, accepted)


__all__ = ["LinkGraphBetaFrontierAccessibilityReport", "evaluate_link_graph_beta_frontier_accessibility"]
