"""Run trace and counters for repeatable beta frontier execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_support import issue_counts, state_counts
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierTraceEvent:
    sequence: int
    stage: str
    record_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierObservabilityReport:
    run_id: str
    events: tuple[LinkGraphBetaFrontierTraceEvent, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "events": [item.to_dict() for item in self.events], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_trace(evaluation: LinkGraphBetaFrontierEvaluation, run_id: str = "link-graph-beta-frontier-run") -> LinkGraphBetaFrontierObservabilityReport:
    event = LinkGraphBetaFrontierTraceEvent(1, "replay", len(evaluation.rows), state_counts(evaluation), issue_counts(evaluation))
    return LinkGraphBetaFrontierObservabilityReport(run_id, (event,), evaluation.accepted)


__all__ = ["LinkGraphBetaFrontierObservabilityReport", "LinkGraphBetaFrontierTraceEvent", "build_link_graph_beta_frontier_trace"]
