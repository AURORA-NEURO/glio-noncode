"""Append-only audit trail for fixture review decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAuditEvent:
    event_id: str
    sequence: int
    event_type: str
    record_id: str
    operation: str
    state: str
    issue_codes: tuple[str, ...]
    previous_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"event_id": self.event_id, "sequence": self.sequence, "event_type": self.event_type, "record_id": self.record_id, "operation": self.operation, "state": self.state, "issue_codes": self.issue_codes, "previous_address": self.previous_address}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAuditTrail:
    fixture_id: str
    events: tuple[LinkGraphFoundationFrontierAuditEvent, ...]
    chain_valid: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def last_address(self) -> str:
        return self.events[-1].content_address if self.events else ""

    def event(self, event_id: str) -> LinkGraphFoundationFrontierAuditEvent:
        return next(item for item in self.events if item.event_id == event_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "events": [item.to_dict() for item in self.events], "chain_valid": self.chain_valid, "accepted": self.accepted, "last_address": self.last_address}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_audit_trail(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierAuditTrail:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_foundation_frontier_fixture_eval", fromlist=["evaluate_link_graph_foundation_frontier_fixture"]).evaluate_link_graph_foundation_frontier_fixture(value)
    events = []
    previous = ""
    for sequence, row in enumerate(replay.rows, start=1):
        event = LinkGraphFoundationFrontierAuditEvent(f"event-{sequence:03d}", sequence, "replay", row.record_id, row.operation, row.observed_state, row.observed_issue_codes, previous)
        events.append(event)
        previous = event.content_address
    values = tuple(events)
    chain = all(event.sequence == index and (event.previous_address == (values[index - 2].content_address if index > 1 else "")) for index, event in enumerate(values, start=1))
    return LinkGraphFoundationFrontierAuditTrail(value.fixture_id, values, chain, bool(values) and chain and replay.accepted)


def audit_trail_summary(trail: LinkGraphFoundationFrontierAuditTrail) -> dict[str, Any]:
    return {"fixture_id": trail.fixture_id, "event_count": len(trail.events), "chain_valid": trail.chain_valid, "first_event": trail.events[0].event_id if trail.events else "", "last_event": trail.events[-1].event_id if trail.events else "", "accepted": trail.accepted}


__all__ = ["LinkGraphFoundationFrontierAuditEvent", "LinkGraphFoundationFrontierAuditTrail", "audit_trail_summary", "build_link_graph_foundation_frontier_audit_trail"]
