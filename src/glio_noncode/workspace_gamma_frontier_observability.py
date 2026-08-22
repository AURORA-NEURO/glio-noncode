"""Structured runtime events for inspection and operational review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_runtime import GammaFrontierRuntimeReport


@dataclass(frozen=True, slots=True)
class GammaFrontierEvent:
    """One ordered event with severity and receipt address."""

    sequence: int
    event_type: str
    stage_id: str | None
    record_id: str | None
    state: str
    severity: str
    address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("event_type", "state", "severity", "address", "detail", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierObservabilityReport:
    """Runtime events grouped by stage and severity."""

    run_id: str
    events: tuple[GammaFrontierEvent, ...]
    content_address: str

    def events_for(self, event_type: str) -> tuple[GammaFrontierEvent, ...]:
        return tuple(item for item in self.events if item.event_type == event_type)

    def by_severity(self, severity: str) -> tuple[GammaFrontierEvent, ...]:
        return tuple(item for item in self.events if item.severity == severity)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "event_count": len(self.events),
            "error_count": len(self.by_severity("error")),
        }


def _event(
    sequence: int,
    event_type: str,
    stage_id: str | None,
    record_id: str | None,
    state: str,
    severity: str,
    address: str,
    detail: str,
) -> GammaFrontierEvent:
    body = {
        "sequence": sequence,
        "event_type": event_type,
        "stage_id": stage_id,
        "record_id": record_id,
        "state": state,
        "severity": severity,
        "address": address,
        "detail": detail,
    }
    return GammaFrontierEvent(**body, content_address=content_hash(body, prefix="event"))


def observe_gamma_frontier(runtime: GammaFrontierRuntimeReport) -> GammaFrontierObservabilityReport:
    """Emit stage start/completion and row-level evidence events."""

    events: list[GammaFrontierEvent] = []
    sequence = 1
    for stage in runtime.stages:
        events.append(
            _event(
                sequence,
                "stage_completed",
                stage.stage_id,
                None,
                stage.state,
                "info" if stage.state in {"complete", "accepted"} else "error",
                stage.output_address,
                stage.detail,
            )
        )
        sequence += 1
    for execution in runtime.evaluation.executions:
        severity = "info" if not execution.issue_codes else "warning"
        events.append(
            _event(
                sequence,
                "record_evaluated",
                None,
                execution.record_id,
                execution.state,
                severity,
                execution.content_address,
                "issue evidence retained"
                if execution.issue_codes
                else "record matched without issues",
            )
        )
        sequence += 1
    body = {"run_id": runtime.run_id, "events": tuple(events)}
    return GammaFrontierObservabilityReport(
        **body, content_address=content_hash(body, prefix="observability")
    )


__all__ = ["GammaFrontierEvent", "GammaFrontierObservabilityReport", "observe_gamma_frontier"]
