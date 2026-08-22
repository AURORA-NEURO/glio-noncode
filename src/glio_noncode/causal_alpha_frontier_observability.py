"""Structured runtime events for alpha frontier execution."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierEvent:
    event_id: str
    run_id: str
    sequence: int
    stage_id: str
    event_type: str
    state: str
    output_address: str
    detail: str
    measurements: dict[str, Any]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"event_id": self.event_id, "run_id": self.run_id, "sequence": self.sequence, "stage_id": self.stage_id, "event_type": self.event_type, "state": self.state, "output_address": self.output_address, "detail": self.detail, "measurements": self.measurements}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierObservabilityReport:
    run_id: str
    events: tuple[CausalAlphaFrontierEvent, ...]
    completed_count: int
    failed_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.events)

    @property
    def total_duration_ms(self) -> float:
        return round(sum(float(item.measurements.get("duration_ms", 0.0)) for item in self.events), 3)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "events": [item.to_dict() for item in self.events], "completed_count": self.completed_count, "failed_count": self.failed_count, "stage_ids": self.stage_ids, "total_duration_ms": self.total_duration_ms, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def record_causal_alpha_frontier_event(run_id: str, sequence: int, stage_id: str, fn: Any, detail: str) -> tuple[Any, CausalAlphaFrontierEvent]:
    started = perf_counter()
    try:
        value = fn()
        address = value.content_address if hasattr(value, "content_address") else content_hash(value)
        return value, CausalAlphaFrontierEvent(f"{run_id}:{sequence}:{stage_id}", run_id, sequence, stage_id, "stage_completed", "completed", address, detail, {"duration_ms": round((perf_counter() - started) * 1000, 3)})
    except Exception as exc:
        return None, CausalAlphaFrontierEvent(f"{run_id}:{sequence}:{stage_id}", run_id, sequence, stage_id, "stage_failed", "failed", "", f"{detail}: {exc}", {"duration_ms": round((perf_counter() - started) * 1000, 3)})


def build_causal_alpha_frontier_observability(run_id: str, events: tuple[CausalAlphaFrontierEvent, ...]) -> CausalAlphaFrontierObservabilityReport:
    return CausalAlphaFrontierObservabilityReport(run_id, events, sum(item.state == "completed" for item in events), sum(item.state == "failed" for item in events), bool(events) and all(item.state == "completed" for item in events))


__all__ = ["CausalAlphaFrontierEvent", "CausalAlphaFrontierObservabilityReport", "build_causal_alpha_frontier_observability", "record_causal_alpha_frontier_event"]
