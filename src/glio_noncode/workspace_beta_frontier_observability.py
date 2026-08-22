"""Structured observability records for projection execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_runtime import BetaFrontierRuntimeReport


@dataclass(frozen=True, slots=True)
class BetaFrontierEvent:
    """One stable event with stage, row, state, and receipt fields."""

    event_id: str
    sequence: int
    event_type: str
    record_id: str | None
    operation: str | None
    state: str
    severity: str
    address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("event_id", "event_type", "state", "severity", "address", "detail", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierObservabilityReport:
    """Event stream with counts and unresolved-state visibility."""

    run_id: str
    events: tuple[BetaFrontierEvent, ...]
    state_counts: dict[str, int]
    severity_counts: dict[str, int]
    content_address: str

    def events_for(self, event_type: str) -> tuple[BetaFrontierEvent, ...]:
        return tuple(item for item in self.events if item.event_type == event_type)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _event(sequence: int, event_type: str, record_id: str | None, operation: str | None, state: str, severity: str, address: str, detail: str) -> BetaFrontierEvent:
    body = {"event_id": f"beta-frontier-event-{sequence:03d}", "sequence": sequence, "event_type": event_type, "record_id": record_id, "operation": operation, "state": state, "severity": severity, "address": address, "detail": detail}
    return BetaFrontierEvent(**body, content_address=content_hash(body))


def observe_beta_frontier(runtime: BetaFrontierRuntimeReport, evaluation: BetaFrontierEvaluation | None = None) -> BetaFrontierObservabilityReport:
    """Emit load, stage, row, issue, and completion events."""

    evaluation = evaluation or runtime.evaluation
    events: list[BetaFrontierEvent] = []
    sequence = 1
    events.append(_event(sequence, "run_started", None, None, "started", "info", runtime.fixture_id, "projection runtime started"))
    sequence += 1
    for stage in runtime.stages:
        events.append(_event(sequence, "stage_completed", None, None, stage.state, "info" if stage.state == "complete" else "error", stage.output_address, stage.detail))
        sequence += 1
    for execution in evaluation.executions:
        severity = "info" if execution.role.value == "positive" else "warning"
        events.append(_event(sequence, "projection_completed", execution.record_id, execution.operation.value, execution.state, severity, execution.content_address, "projection output retained"))
        sequence += 1
        for issue in execution.issue_codes:
            events.append(_event(sequence, "issue_retained", execution.record_id, execution.operation.value, execution.state, "warning", execution.content_address, issue))
            sequence += 1
    events.append(_event(sequence, "run_completed", None, None, "complete" if runtime.accepted else "failed", "info" if runtime.accepted else "error", runtime.content_address, "projection runtime completed"))
    state_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for event in events:
        state_counts[event.state] = state_counts.get(event.state, 0) + 1
        severity_counts[event.severity] = severity_counts.get(event.severity, 0) + 1
    body = {"run_id": runtime.run_id, "events": tuple(events), "state_counts": state_counts, "severity_counts": severity_counts}
    return BetaFrontierObservabilityReport(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierEvent", "BetaFrontierObservabilityReport", "observe_beta_frontier"]
