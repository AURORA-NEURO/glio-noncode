"""Structured stage observations for platform runtime operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class PlatformFrontierStageObservation:
    stage_id: str
    sequence: int
    state: str
    output_address: str
    events: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierTrace:
    run_id: str
    observations: tuple[PlatformFrontierStageObservation, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_trace(run_id: str, stages: tuple[dict[str, Any], ...], *, accepted: bool) -> PlatformFrontierTrace:
    require_non_empty(run_id, "run_id")
    observations = []
    for sequence, stage in enumerate(stages, start=1):
        body = {"stage_id": str(stage["stage_id"]), "sequence": sequence, "state": str(stage.get("state", "completed")), "output_address": str(stage["output_address"]), "events": tuple(str(item) for item in stage.get("events", ())) }
        observations.append(PlatformFrontierStageObservation(**body, content_address=content_hash(body)))
    return PlatformFrontierTrace(run_id, tuple(observations), accepted and all(item.output_address.startswith("sha256:") for item in observations), content_hash(tuple(observations)))


__all__ = ["PlatformFrontierStageObservation", "PlatformFrontierTrace", "build_platform_frontier_trace"]
