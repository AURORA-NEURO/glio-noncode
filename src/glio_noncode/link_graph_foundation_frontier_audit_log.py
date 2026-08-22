"""Stage and review audit events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_pipeline import LinkGraphFoundationFrontierPipelineReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAuditEvent:
    event_id: str
    event_kind: str
    subject_id: str
    disposition: str
    evidence_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAuditLog:
    events: tuple[LinkGraphFoundationFrontierAuditEvent, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"events": [item.to_dict() for item in self.events], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_audit_log(pipeline: LinkGraphFoundationFrontierPipelineReport) -> LinkGraphFoundationFrontierAuditLog:
    events = tuple(LinkGraphFoundationFrontierAuditEvent(content_hash(("stage", item.stage_id, pipeline.content_address)), "stage", item.stage_id, item.status, pipeline.content_address) for item in pipeline.stages) + tuple(LinkGraphFoundationFrontierAuditEvent(content_hash(("review", item.record_id, pipeline.review_queue.content_address)), "review", item.record_id, item.disposition, pipeline.evaluation.content_address) for item in pipeline.review_queue.entries)
    return LinkGraphFoundationFrontierAuditLog(events, bool(events) and all(item.evidence_address.startswith("sha256:") for item in events))


__all__ = ["LinkGraphFoundationFrontierAuditEvent", "LinkGraphFoundationFrontierAuditLog", "build_link_graph_foundation_frontier_audit_log"]
