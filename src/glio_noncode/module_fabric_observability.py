"""Stage and record observations for module-fabric runtime diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_fabric_contracts import FabricRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FabricObservation:
    observation_id: str
    ordinal: int
    stage_id: str
    state: str
    input_address: str
    output_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricTrace:
    run_id: str
    observations: tuple[FabricObservation, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_module_fabric_trace(report: FabricRuntimeReport) -> FabricTrace:
    observations = tuple(
        FabricObservation(
            observation_id=f"{report.run_id}:{stage.stage_id}",
            ordinal=stage.ordinal,
            stage_id=stage.stage_id,
            state=stage.state.value,
            input_address=stage.input_address,
            output_address=stage.output_address,
            detail=stage.detail,
        )
        for stage in report.stages
    )
    accepted = tuple(item.ordinal for item in observations) == tuple(range(1, len(observations) + 1)) and all(item.input_address and item.output_address for item in observations)
    body = {"run_id": report.run_id, "observations": observations, "accepted": accepted}
    return FabricTrace(report.run_id, observations, accepted, content_hash(body, prefix="module-fabric-trace"))


def verify_module_fabric_trace(trace: FabricTrace) -> tuple[str, ...]:
    issues: list[str] = []
    if not trace.observations:
        issues.append("empty_trace")
    if tuple(item.ordinal for item in trace.observations) != tuple(range(1, len(trace.observations) + 1)):
        issues.append("ordinal_gap")
    if any(not item.input_address or not item.output_address for item in trace.observations):
        issues.append("missing_stage_address")
    return tuple(issues)


__all__ = ["FabricObservation", "FabricTrace", "build_module_fabric_trace", "verify_module_fabric_trace"]
