"""Trace and observability records for the context frontier runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_runtime import ChromatinContextFrontierRuntimeReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierTraceEvent:
    sequence: int
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.sequence < 1 or not self.stage_id or not self.detail:
            raise ValidationError("trace event is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierObservabilityReport:
    run_id: str
    events: tuple[ChromatinContextFrontierTraceEvent, ...]
    counters: dict[str, int]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.run_id or len(self.events) != 10:
            raise ValidationError("observability report requires ten events")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def event(self, stage_id: str) -> ChromatinContextFrontierTraceEvent:
        for item in self.events:
            if item.stage_id == stage_id:
                return item
        raise KeyError(stage_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_context_frontier_trace(
    runtime: ChromatinContextFrontierRuntimeReport,
) -> ChromatinContextFrontierObservabilityReport:
    events = tuple(
        ChromatinContextFrontierTraceEvent(
            index, stage.stage_id, stage.status, stage.input_count, stage.output_count, stage.detail
        )
        for index, stage in enumerate(runtime.stages, start=1)
    )
    counters = {
        "stage_count": len(events),
        "failed_stage_count": sum(item.status != "passed" for item in events),
        "record_count": len(runtime.evaluation.records),
        "positive_count": len(runtime.evaluation.positive_rows),
        "control_count": len(runtime.evaluation.control_rows),
        "review_count": runtime.policy.review_count,
        "refusal_count": runtime.policy.refusal_count,
        "source_count": len(runtime.data.checks),
    }
    return ChromatinContextFrontierObservabilityReport(
        runtime.run_id, events, counters, runtime.accepted
    )


__all__ = [
    "ChromatinContextFrontierObservabilityReport",
    "ChromatinContextFrontierTraceEvent",
    "build_chromatin_context_frontier_trace",
]
