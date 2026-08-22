"""Structured observability for Domain 13 planning runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_runtime import ValidationFrontierRuntimeReport


@dataclass(frozen=True, slots=True)
class ValidationFrontierEvent:
    event_id: str
    event_kind: str
    subject_id: str
    state: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierObservabilityReport:
    run_id: str
    events: tuple[ValidationFrontierEvent, ...]
    counters: tuple[tuple[str, int], ...]
    content_address: str

    def counter_map(self) -> dict[str, int]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"counter_map": self.counter_map()}


def observe_validation_frontier(runtime: ValidationFrontierRuntimeReport, evaluation: ValidationFrontierEvaluation) -> ValidationFrontierObservabilityReport:
    events: list[ValidationFrontierEvent] = []
    for stage in runtime.stages:
        body = {"event_id": f"stage:{stage.stage_id}", "event_kind": "runtime_stage", "subject_id": stage.stage_id, "state": stage.state, "detail": stage.detail}
        events.append(ValidationFrontierEvent(**body, content_address=content_hash(body)))
    for execution in evaluation.executions:
        body = {"event_id": f"execution:{execution.record_id}", "event_kind": "record_execution", "subject_id": execution.record_id, "state": execution.state, "detail": ";".join(execution.issue_codes) or "accepted path"}
        events.append(ValidationFrontierEvent(**body, content_address=content_hash(body)))
    counters = (("runtime_stage_count", len(runtime.stages)), ("execution_count", len(evaluation.executions)), ("accepted_execution_count", sum(item.accepted for item in evaluation.executions)), ("positive_count", sum(item.role.value == "positive" for item in evaluation.executions)), ("control_count", sum(item.role.value == "control" for item in evaluation.executions)), ("issue_count", sum(bool(item.issue_codes) for item in evaluation.executions)), ("ready_count", sum(item.state == "ready_for_review" for item in evaluation.executions)), ("blocked_count", sum(item.state == "blocked" for item in evaluation.executions)), ("partial_count", sum(item.state == "partial" for item in evaluation.executions)))
    body = {"run_id": runtime.run_id, "events": tuple(events), "counters": counters}
    return ValidationFrontierObservabilityReport(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierEvent", "ValidationFrontierObservabilityReport", "observe_validation_frontier"]
