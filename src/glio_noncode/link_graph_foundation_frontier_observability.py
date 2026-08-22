"""Stage events for local and Actions runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierEvent:
    event_id: str
    stage_id: str
    status: str
    record_count: int
    occurred_at: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierObservabilityReport:
    run_id: str
    events: tuple[LinkGraphFoundationFrontierEvent, ...]
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


def build_link_graph_foundation_frontier_trace(evaluation: LinkGraphFoundationFrontierEvaluation, run_id: str) -> LinkGraphFoundationFrontierObservabilityReport:
    timestamp = datetime.now(timezone.utc).isoformat()
    stages = ("fixture", "contracts", "sources", "replay", "schema", "quality", "policy", "depth", "validation", "integrity", "release", "review")
    events = tuple(LinkGraphFoundationFrontierEvent(content_hash((run_id, stage, evaluation.content_address)), stage, "passed" if evaluation.accepted else "failed", len(evaluation.rows), timestamp) for stage in stages)
    return LinkGraphFoundationFrontierObservabilityReport(run_id, events, len(events) == 12 and evaluation.accepted)


__all__ = ["LinkGraphFoundationFrontierEvent", "LinkGraphFoundationFrontierObservabilityReport", "build_link_graph_foundation_frontier_trace"]
