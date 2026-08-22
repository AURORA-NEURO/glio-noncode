"""Stage receipts and trace events for local and Actions execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierEvent:
    event_id: str
    stage_id: str
    event_kind: str
    status: str
    record_count: int
    detail: str
    occurred_at: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierObservabilityReport:
    run_id: str
    events: tuple[LinkGraphAlphaFrontierEvent, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def event(self, stage_id: str) -> LinkGraphAlphaFrontierEvent:
        for item in self.events:
            if item.stage_id == stage_id:
                return item
        raise KeyError(stage_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "events": [item.to_dict() for item in self.events], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_trace(evaluation: LinkGraphAlphaFrontierEvaluation, run_id: str) -> LinkGraphAlphaFrontierObservabilityReport:
    timestamp = datetime.now(timezone.utc).isoformat()
    stages = ("fixture", "contracts", "sources", "replay", "schema", "quality", "policy", "depth", "validation", "integrity", "release", "review")
    events = tuple(LinkGraphAlphaFrontierEvent(content_hash((run_id, stage, evaluation.content_address)), stage, "stage", "passed" if evaluation.accepted else "failed", len(evaluation.rows), "deterministic stage receipt", timestamp) for stage in stages)
    return LinkGraphAlphaFrontierObservabilityReport(run_id, events, len(events) == 12 and all(item.status == "passed" for item in events))


def link_graph_alpha_frontier_review_budget(report: LinkGraphAlphaFrontierObservabilityReport, *, maximum_events: int = 32) -> dict[str, Any]:
    return {"run_id": report.run_id, "event_count": len(report.events), "maximum_events": maximum_events, "within_budget": len(report.events) <= maximum_events}


__all__ = ["LinkGraphAlphaFrontierEvent", "LinkGraphAlphaFrontierObservabilityReport", "build_link_graph_alpha_frontier_trace", "link_graph_alpha_frontier_review_budget"]
