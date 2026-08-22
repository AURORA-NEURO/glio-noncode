"""Structured runtime trace for the Domain 08 context plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_runtime import CellContextFrontierRuntimeReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierTraceEvent:
    sequence: int
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.sequence < 1 or not self.stage_id or not self.detail:
            raise ValidationError("cell trace event is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierObservabilityReport:
    run_id: str
    events: tuple[CellContextFrontierTraceEvent, ...]
    counters: dict[str, int]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.run_id or len(self.events) != 10:
            raise ValidationError("cell trace requires ten events")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def event(self, stage_id: str) -> CellContextFrontierTraceEvent:
        for item in self.events:
            if item.stage_id == stage_id:
                return item
        raise KeyError(stage_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_trace(
    runtime: CellContextFrontierRuntimeReport,
) -> CellContextFrontierObservabilityReport:
    events = tuple(
        CellContextFrontierTraceEvent(
            index, item.stage_id, item.status, item.input_count, item.output_count, item.detail
        )
        for index, item in enumerate(runtime.stages, start=1)
    )
    counters = {
        "stage_count": 10,
        "failed_stage_count": sum(item.status != "passed" for item in events),
        "record_count": len(runtime.evaluation.records),
        "positive_count": len(runtime.evaluation.positive_rows),
        "control_count": len(runtime.evaluation.control_rows),
        "review_count": runtime.policy.review_count,
        "refusal_count": runtime.policy.refusal_count,
        "source_count": len(runtime.data.checks),
    }
    return CellContextFrontierObservabilityReport(
        runtime.run_id, events, counters, runtime.accepted
    )


__all__ = [
    "CellContextFrontierObservabilityReport",
    "CellContextFrontierTraceEvent",
    "build_cell_context_frontier_trace",
]
