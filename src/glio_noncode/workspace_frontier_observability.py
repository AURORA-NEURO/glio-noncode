"""Structured observability events for workspace execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_runtime import WorkspaceFrontierRuntimeReport


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierEvent:
    event_id: str
    sequence: int
    event_type: str
    record_id: str | None
    state: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierObservabilityReport:
    run_id: str
    events: tuple[WorkspaceFrontierEvent, ...]
    accepted: bool
    content_address: str

    def by_type(self, event_type: str) -> tuple[WorkspaceFrontierEvent, ...]:
        return tuple(item for item in self.events if item.event_type == event_type)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _event(event_id: str, sequence: int, event_type: str, record_id: str | None, state: str, detail: str) -> WorkspaceFrontierEvent:
    body = {"event_id": event_id, "sequence": sequence, "event_type": event_type, "record_id": record_id, "state": state, "detail": detail}
    return WorkspaceFrontierEvent(**body, content_address=content_hash(body))


def observe_workspace_frontier(runtime: WorkspaceFrontierRuntimeReport, evaluation: WorkspaceFrontierEvaluation) -> WorkspaceFrontierObservabilityReport:
    events: list[WorkspaceFrontierEvent] = []
    for stage in runtime.stages:
        events.append(_event(f"stage:{stage.stage_id}", stage.sequence, "runtime_stage", None, stage.state, stage.detail))
    offset = len(events)
    for index, execution in enumerate(evaluation.executions, start=1):
        events.append(_event(f"execution:{execution.record_id}", offset + index, "surface_execution", execution.record_id, execution.state, execution.operation.value))
    body = {"run_id": runtime.run_id, "events": tuple(events), "accepted": runtime.accepted and all(item.content_address.startswith("sha256:") for item in events)}
    return WorkspaceFrontierObservabilityReport(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierEvent", "WorkspaceFrontierObservabilityReport", "observe_workspace_frontier"]
