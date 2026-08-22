"""Trace and event records for deterministic execution inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_runtime import SequenceRegulationRuntimeReport
from .sequence_regulation_frontier_views import SequenceRegulationView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationTraceEvent:
    event_id: str
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.event_id or not self.stage_id or not self.detail:
            raise ValidationError("trace event is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationTrace:
    run_id: str
    events: tuple[SequenceRegulationTraceEvent, ...]
    record_events: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.events:
            raise ValidationError("trace requires events")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_regulation_trace(
    runtime: SequenceRegulationRuntimeReport,
    view: SequenceRegulationView,
) -> SequenceRegulationTrace:
    stage_events = tuple(
        SequenceRegulationTraceEvent(
            f"event:{stage.stage_id}",
            stage.stage_id,
            stage.status,
            stage.input_count,
            stage.output_count,
            stage.detail,
        )
        for stage in runtime.stages
    )
    record_events = sum(1 for row in view.rows if row.result_address.startswith("sha256:"))
    events = stage_events + (
        SequenceRegulationTraceEvent(
            "event:records",
            "records",
            "passed" if record_events == len(view.rows) else "failed",
            len(view.rows),
            record_events,
            "record result receipts observed",
        ),
    )
    return SequenceRegulationTrace(
        runtime.run_id, events, record_events, runtime.accepted and record_events == len(view.rows)
    )


__all__ = [
    "SequenceRegulationTrace",
    "SequenceRegulationTraceEvent",
    "build_sequence_regulation_trace",
]
