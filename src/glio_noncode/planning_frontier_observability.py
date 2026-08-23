"""Structured execution events for runtime inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .planning_frontier_runtime import PlanningRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningObservability:
    run_id: str
    events: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def observe_planning(run_id: str, stages: Iterable[PlanningRuntimeStage]) -> PlanningObservability:
    events = tuple({"sequence": item.sequence, "stage_id": item.stage_id, "state": item.state, "accepted": item.accepted, "output_address": item.output_address} for item in stages)
    body = {"run_id": run_id, "events": events, "accepted": bool(run_id and events and tuple(item["sequence"] for item in events) == tuple(range(1, len(events) + 1)))}
    return PlanningObservability(**body, content_address=content_hash(body, prefix="planning-observability"))


__all__ = ["PlanningObservability", "observe_planning"]
