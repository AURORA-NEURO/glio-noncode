"""Structured events for the C09-C12 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .cohort_alpha_frontier_runtime_types import CohortAlphaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierEvent:
    event_id: str
    fixture_id: str
    ordinal: int
    stage_id: str
    accepted: bool
    output_address: str
    emitted_at: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierObservabilityReport:
    fixture_id: str
    events: tuple[CohortAlphaFrontierEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def observe_cohort_alpha_frontier(fixture_id: str, stages: Iterable[CohortAlphaFrontierRuntimeStage], *, emitted_at: str) -> CohortAlphaFrontierObservabilityReport:
    events = []
    for stage in stages:
        body = {"event_id": f"{fixture_id}:{stage.ordinal}", "fixture_id": fixture_id, "ordinal": stage.ordinal, "stage_id": stage.stage_id, "accepted": stage.accepted, "output_address": stage.output_address, "emitted_at": emitted_at}
        events.append(CohortAlphaFrontierEvent(body["event_id"], fixture_id, stage.ordinal, stage.stage_id, stage.accepted, stage.output_address, emitted_at, content_hash(body, prefix="alpha-event")))
    values = tuple(events)
    return CohortAlphaFrontierObservabilityReport(fixture_id, values, bool(values) and all(item.accepted for item in values), content_hash(values, prefix="alpha-observability"))


__all__ = ["CohortAlphaFrontierEvent", "CohortAlphaFrontierObservabilityReport", "observe_cohort_alpha_frontier"]
