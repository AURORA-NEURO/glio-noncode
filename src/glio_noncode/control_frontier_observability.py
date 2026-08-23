"""Stage and event trace for control frontier runtime operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ControlFrontierStageObservation:
    stage_id: str
    sequence: int
    state: str
    output_address: str
    events: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierTrace:
    run_id: str
    stages: tuple[ControlFrontierStageObservation, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_trace(run_id: str, stages: Iterable[dict[str, Any]], *, accepted: bool) -> ControlFrontierTrace:
    require_non_empty(run_id, "run_id")
    rows = []
    for index, value in enumerate(stages, start=1):
        body = {"stage_id": str(value["stage_id"]), "sequence": index, "state": str(value.get("state", "completed")), "output_address": str(value["output_address"]), "events": tuple(str(item) for item in value.get("events", ())) }
        rows.append(ControlFrontierStageObservation(**body, content_address=content_hash(body)))
    return ControlFrontierTrace(run_id, tuple(rows), accepted, content_hash({"run_id": run_id, "stages": tuple(rows), "accepted": accepted}))


__all__ = ["ControlFrontierStageObservation", "ControlFrontierTrace", "build_control_frontier_trace"]
