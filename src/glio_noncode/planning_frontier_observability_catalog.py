"""Structured event catalog for planning runtime observability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from .planning_frontier_runtime import PlanningRuntimeStage
from .serialization import content_hash, jsonable


class PlanningEventKind(StrEnum):
    START = "start"
    SOURCE_AUDIT = "source_audit"
    ADAPTER_LOAD = "adapter_load"
    SCHEMA_LOAD = "schema_load"
    EVALUATION = "evaluation"
    QUALITY = "quality"
    ASSURANCE = "assurance"
    HELD = "held"
    RELEASE = "release"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class PlanningEventDefinition:
    event_kind: PlanningEventKind
    required_fields: tuple[str, ...]
    emitted_by: str
    consumer_use: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningTraceEvent:
    sequence: int
    run_id: str
    event_kind: PlanningEventKind
    stage_id: str
    accepted: bool
    state: str
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningTrace:
    run_id: str
    events: tuple[PlanningTraceEvent, ...]
    state_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def planning_event_catalog() -> tuple[PlanningEventDefinition, ...]:
    rows = (
        (PlanningEventKind.START, ("run_id",), "runtime", "identify a run"),
        (PlanningEventKind.SOURCE_AUDIT, ("stage_id", "output_address"), "data-audit", "inspect public receipt closure"),
        (PlanningEventKind.ADAPTER_LOAD, ("stage_id", "output_address"), "adapters", "inspect operation closure"),
        (PlanningEventKind.SCHEMA_LOAD, ("stage_id", "output_address"), "schema", "inspect required inputs"),
        (PlanningEventKind.EVALUATION, ("stage_id", "output_address"), "fixture-evaluation", "inspect scenario results"),
        (PlanningEventKind.QUALITY, ("stage_id", "output_address"), "quality-gate", "inspect blocking checks"),
        (PlanningEventKind.ASSURANCE, ("stage_id", "output_address"), "assurance", "inspect release planes"),
        (PlanningEventKind.HELD, ("stage_id", "state"), "review queue", "route held rows"),
        (PlanningEventKind.RELEASE, ("stage_id", "output_address"), "release", "inspect bounded release"),
        (PlanningEventKind.COMPLETE, ("run_id", "accepted"), "runtime", "close run"),
    )
    definitions = []
    for event_kind, fields, emitted_by, use in rows:
        body = {"event_kind": event_kind, "required_fields": fields, "emitted_by": emitted_by, "consumer_use": use}
        definitions.append(PlanningEventDefinition(**body, content_address=content_hash(body, prefix="planning-event-definition")))
    return tuple(definitions)


def _event_kind(stage_id: str, accepted: bool, state: str) -> PlanningEventKind:
    normalized = stage_id.lower()
    if normalized == "data-audit":
        return PlanningEventKind.SOURCE_AUDIT
    if normalized == "adapters":
        return PlanningEventKind.ADAPTER_LOAD
    if normalized == "schema":
        return PlanningEventKind.SCHEMA_LOAD
    if normalized == "fixture-evaluation":
        return PlanningEventKind.EVALUATION
    if normalized == "quality-gate":
        return PlanningEventKind.QUALITY
    if normalized == "assurance":
        return PlanningEventKind.ASSURANCE
    if normalized in {"release", "final-acceptance"}:
        return PlanningEventKind.RELEASE
    if not accepted or state == "held":
        return PlanningEventKind.HELD
    return PlanningEventKind.COMPLETE


def build_planning_trace(run_id: str, stages: Iterable[PlanningRuntimeStage]) -> PlanningTrace:
    events = []
    for stage in stages:
        kind = _event_kind(stage.stage_id, stage.accepted, stage.state)
        body = {"sequence": stage.sequence, "run_id": run_id, "event_kind": kind, "stage_id": stage.stage_id, "accepted": stage.accepted, "state": stage.state, "output_address": stage.output_address}
        events.append(PlanningTraceEvent(**body, content_address=content_hash(body, prefix="planning-trace-event")))
    state_counts: dict[str, int] = {}
    for event in events:
        state_counts[event.state] = state_counts.get(event.state, 0) + 1
    accepted = bool(events and tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1)) and all(item.output_address for item in events))
    body = {"run_id": run_id, "events": tuple(events), "state_counts": state_counts, "accepted": accepted}
    return PlanningTrace(run_id, tuple(events), state_counts, accepted, content_hash(body, prefix="planning-trace"))


__all__ = [
    "PlanningEventDefinition",
    "PlanningEventKind",
    "PlanningTrace",
    "PlanningTraceEvent",
    "build_planning_trace",
    "planning_event_catalog",
]
