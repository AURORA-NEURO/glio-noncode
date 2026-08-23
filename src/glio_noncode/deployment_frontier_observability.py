"""Ordered trace ledger for deployment frontier runtime stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierStageObservation:
    sequence: int
    stage_id: str
    state: str
    output_address: str
    event_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierTrace:
    run_id: str
    observations: tuple[DeploymentFrontierStageObservation, ...]
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.observations)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def build_deployment_frontier_trace(run_id: str, stages: tuple[dict[str, Any], ...], *, accepted: bool) -> DeploymentFrontierTrace:
    observations = []
    for sequence, raw in enumerate(stages, start=1):
        body = {"sequence": sequence, "stage_id": str(raw["stage_id"]), "state": str(raw.get("state", "completed")), "output_address": str(raw.get("output_address", "")), "event_codes": tuple(str(item) for item in raw.get("events", ())) }
        observations.append(DeploymentFrontierStageObservation(**body, content_address=deployment_address(body)))
    ordered = tuple(item.sequence for item in observations) == tuple(range(1, len(observations) + 1))
    return DeploymentFrontierTrace(run_id, tuple(observations), accepted and ordered, deployment_address(tuple(observations)))


__all__ = ["DeploymentFrontierStageObservation", "DeploymentFrontierTrace", "build_deployment_frontier_trace"]
