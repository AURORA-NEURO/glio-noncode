"""Structured runtime events for audit and operator inspection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFoundationEvent:
    event_id: str
    ordinal: int
    stage_id: str
    status: str
    detail: str
    output_address: str
    emitted_at: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationObservabilityReport:
    report_id: str
    fixture_id: str
    events: tuple[CohortFoundationEvent, ...]
    accepted: bool
    content_address: str

    @property
    def failed_events(self) -> tuple[CohortFoundationEvent, ...]:
        return tuple(item for item in self.events if item.status != "accepted")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def observe_cohort_foundation_frontier(fixture_id: str, stages: Iterable[Any], *, emitted_at: str | None = None) -> CohortFoundationObservabilityReport:
    timestamp = emitted_at or datetime.now(UTC).isoformat()
    events = []
    for index, stage in enumerate(stages, start=1):
        status = "accepted" if stage.accepted else "failed"
        body = {"ordinal": index, "stage_id": stage.stage_id, "status": status, "address": stage.output_address}
        events.append(CohortFoundationEvent(content_hash((fixture_id, stage.stage_id, index), prefix="event"), index, stage.stage_id, status, stage.detail, stage.output_address, timestamp, content_hash(body)))
    body = {"report_id": "cohort-foundation-frontier-observability", "fixture_id": fixture_id, "events": events}
    return CohortFoundationObservabilityReport(body["report_id"], fixture_id, tuple(events), not any(item.status != "accepted" for item in events), content_hash(body))


__all__ = ["CohortFoundationEvent", "CohortFoundationObservabilityReport", "observe_cohort_foundation_frontier"]
