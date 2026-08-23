"""Executable runbook and stop conditions for coordination operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_contracts import CoordinationRuntime, addressed


@dataclass(frozen=True, slots=True)
class CoordinationRunbookStep:
    ordinal: int
    stage_id: str
    action: str
    required_receipt: str
    stop_condition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "stage_id": self.stage_id,
            "action": self.action,
            "required_receipt": self.required_receipt,
            "stop_condition": self.stop_condition,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class CoordinationRunbook:
    runbook_id: str
    steps: tuple[CoordinationRunbookStep, ...]
    stop_conditions: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "runbook_id": self.runbook_id,
            "steps": tuple(item.to_dict() for item in self.steps),
            "stop_conditions": self.stop_conditions,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def build_coordination_runbook(runtime: CoordinationRuntime) -> CoordinationRunbook:
    steps = []
    for stage in runtime.stages:
        body = {
            "ordinal": stage.ordinal,
            "stage_id": stage.stage_id,
            "action": stage.detail,
            "required_receipt": stage.content_address,
            "stop_condition": "stop if stage state is not accepted",
        }
        steps.append(CoordinationRunbookStep(**body, content_address=addressed(body, "coordination-runbook-step")))
    stop_conditions = (
        "stop on public-data audit failure",
        "stop on dependency cycle or budget overflow",
        "stop on unsafe payload or network request",
        "stop before release when any quality check fails",
        "never promote a held control through recovery routing",
    )
    body = {"runbook_id": f"{runtime.run_id}:runbook", "steps": tuple(steps), "stop_conditions": stop_conditions, "accepted": len(steps) == 20}
    return CoordinationRunbook(**body, content_address=addressed(body, "coordination-runbook"))


def runbook_is_executable(runbook: CoordinationRunbook) -> bool:
    return runbook.accepted and tuple(item.ordinal for item in runbook.steps) == tuple(range(1, len(runbook.steps) + 1)) and all(item.required_receipt for item in runbook.steps)


__all__ = ["CoordinationRunbookStep", "CoordinationRunbook", "build_coordination_runbook", "runbook_is_executable"]
