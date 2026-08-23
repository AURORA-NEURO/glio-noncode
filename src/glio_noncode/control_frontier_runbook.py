"""Executable review runbook for control frontier release operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierRunbookStep:
    step_id: str
    sequence: int
    command: str
    stop_condition: str
    evidence: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierRunbook:
    runbook_id: str
    steps: tuple[ControlFrontierRunbookStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_runbook() -> ControlFrontierRunbook:
    specs = (
        ("audit", "audit-control-frontier-data", "stop on boundary mismatch", "data audit"),
        ("evaluate", "evaluate-control-frontier", "stop on failed positive row", "evaluation receipt"),
        ("reconcile", "reconcile-control-frontier", "stop on state or issue mismatch", "reconciliation"),
        ("quality", "quality-gate-control-frontier", "stop on blocking rule", "quality gate"),
        ("replay", "replay-control-frontier", "stop on address mismatch", "replay receipt"),
        ("release", "release-control-frontier", "do not publish if not research-only", "release manifest"),
    )
    steps = []
    for sequence, (step_id, command, stop_condition, evidence) in enumerate(specs, start=1):
        body = {"step_id": step_id, "sequence": sequence, "command": command, "stop_condition": stop_condition, "evidence": evidence}
        steps.append(ControlFrontierRunbookStep(**body, content_address=content_hash(body)))
    return ControlFrontierRunbook("control-frontier-release-runbook", tuple(steps), True, content_hash(tuple(steps)))


__all__ = ["ControlFrontierRunbook", "ControlFrontierRunbookStep", "build_control_frontier_runbook"]
