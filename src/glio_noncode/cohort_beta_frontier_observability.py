"""Structured execution events for audit and operational monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .cohort_beta_frontier_runtime_types import CohortBetaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierEvent:
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
class CohortBetaFrontierObservabilityReport:
    fixture_id: str
    events: tuple[CohortBetaFrontierEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def observe_cohort_beta_frontier(fixture_id: str, stages: Iterable[CohortBetaFrontierRuntimeStage], *, emitted_at: str) -> CohortBetaFrontierObservabilityReport:
    events = []
    for stage in stages:
        body = {"event_id": f"{fixture_id}:{stage.ordinal}", "fixture_id": fixture_id, "ordinal": stage.ordinal, "stage_id": stage.stage_id, "accepted": stage.accepted, "output_address": stage.output_address, "emitted_at": emitted_at}
        events.append(CohortBetaFrontierEvent(body["event_id"], fixture_id, stage.ordinal, stage.stage_id, stage.accepted, stage.output_address, emitted_at, content_hash(body, prefix="event")))
    values = tuple(events)
    return CohortBetaFrontierObservabilityReport(fixture_id, values, bool(values) and all(item.accepted for item in values), content_hash(values, prefix="observability"))


__all__ = ["CohortBetaFrontierEvent", "CohortBetaFrontierObservabilityReport", "observe_cohort_beta_frontier"]
