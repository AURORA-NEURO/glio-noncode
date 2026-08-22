"""Audit events for release, review, and boundary decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierAuditEvent:
    event_id: str
    event_kind: str
    subject_id: str
    disposition: str
    evidence_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierAuditLog:
    events: tuple[LinkGraphAlphaFrontierAuditEvent, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_kind(self, event_kind: str) -> tuple[LinkGraphAlphaFrontierAuditEvent, ...]:
        return tuple(item for item in self.events if item.event_kind == event_kind)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"events": [item.to_dict() for item in self.events], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_audit_log(pipeline: LinkGraphAlphaFrontierPipelineReport) -> LinkGraphAlphaFrontierAuditLog:
    events = [LinkGraphAlphaFrontierAuditEvent(content_hash(("stage", item.stage_id, pipeline.content_address)), "stage", item.stage_id, item.status, pipeline.content_address, item.detail) for item in pipeline.stages]
    events.extend(LinkGraphAlphaFrontierAuditEvent(content_hash(("review", item.record_id, pipeline.review_queue.content_address)), "review", item.record_id, item.disposition, pipeline.evaluation.content_address, item.rationale) for item in pipeline.review_queue.entries)
    values = tuple(events)
    return LinkGraphAlphaFrontierAuditLog(values, bool(values) and all(item.evidence_address.startswith("sha256:") for item in values))


__all__ = ["LinkGraphAlphaFrontierAuditEvent", "LinkGraphAlphaFrontierAuditLog", "build_link_graph_alpha_frontier_audit_log"]
