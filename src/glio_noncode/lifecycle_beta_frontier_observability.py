"""Stage and event observability for a lifecycle beta run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierEvent:
    event_id: str
    stage_id: str
    severity: str
    message: str
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierStageObservation:
    stage_id: str
    sequence: int
    state: str
    output_address: str
    duration_ms: float
    event_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierTrace:
    run_id: str
    stages: tuple[LifecycleBetaFrontierStageObservation, ...]
    events: tuple[LifecycleBetaFrontierEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_trace(run_id: str, stage_rows: tuple[dict[str, Any], ...], *, accepted: bool) -> LifecycleBetaFrontierTrace:
    stages = []
    events = []
    for row in stage_rows:
        body = {"stage_id": row["stage_id"], "sequence": row["sequence"], "state": row["state"], "output_address": row["output_address"], "duration_ms": row.get("duration_ms", 0.0), "event_count": len(row.get("events", ()))}
        stages.append(LifecycleBetaFrontierStageObservation(**body, content_address=content_hash(body)))
        for index, message in enumerate(row.get("events", ()), 1):
            event_body = {"event_id": content_hash({"run_id": run_id, "stage": row["stage_id"], "index": index}, prefix="event"), "stage_id": row["stage_id"], "severity": "info", "message": str(message), "output_address": row["output_address"]}
            events.append(LifecycleBetaFrontierEvent(**event_body, content_address=content_hash(event_body)))
    body = {"run_id": run_id, "stages": tuple(stages), "events": tuple(events), "accepted": accepted}
    return LifecycleBetaFrontierTrace(**body, content_address=content_hash(body))


def lifecycle_beta_frontier_review_budget(trace: LifecycleBetaFrontierTrace) -> dict[str, Any]:
    return {"run_id": trace.run_id, "stage_count": len(trace.stages), "event_count": len(trace.events), "accepted": trace.accepted, "content_address": trace.content_address}


__all__ = ["LifecycleBetaFrontierEvent", "LifecycleBetaFrontierStageObservation", "LifecycleBetaFrontierTrace", "build_lifecycle_beta_frontier_trace", "lifecycle_beta_frontier_review_budget"]
