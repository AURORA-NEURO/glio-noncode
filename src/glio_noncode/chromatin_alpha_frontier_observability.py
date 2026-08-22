"""Structured runtime events for chromatin-alpha inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_runtime import ChromatinAlphaFrontierRuntimeReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierEvent:
    sequence: int
    event_type: str
    stage_id: str | None
    record_id: str | None
    state: str
    severity: str
    address: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            self.sequence < 1
            or not self.event_type
            or not self.state
            or not self.severity
            or not self.address
            or not self.detail
        ):
            raise ValidationError("event is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierObservabilityReport:
    run_id: str
    events: tuple[ChromatinAlphaFrontierEvent, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.run_id or not self.events:
            raise ValidationError("observability requires events")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def events_for(self, event_type: str) -> tuple[ChromatinAlphaFrontierEvent, ...]:
        return tuple(event for event in self.events if event.event_type == event_type)

    def by_severity(self, severity: str) -> tuple[ChromatinAlphaFrontierEvent, ...]:
        return tuple(event for event in self.events if event.severity == severity)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "event_count": len(self.events),
            "error_count": len(self.by_severity("error")),
            "warning_count": len(self.by_severity("warning")),
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
) -> ChromatinAlphaFrontierEvent:
    return ChromatinAlphaFrontierEvent(
        sequence, event_type, stage_id, record_id, state, severity, address, detail
    )


def build_chromatin_alpha_frontier_trace(
    runtime: ChromatinAlphaFrontierRuntimeReport,
) -> ChromatinAlphaFrontierObservabilityReport:
    events: list[ChromatinAlphaFrontierEvent] = []
    sequence = 1
    for stage in runtime.stages:
        events.append(
            _event(
                sequence,
                "stage_completed",
                stage.stage_id,
                None,
                stage.status,
                "info" if stage.status == "passed" else "error",
                stage.content_address,
                stage.detail,
            )
        )
        sequence += 1
    for item in runtime.evaluation.records:
        severity = "info" if item.accepted and not item.observed_issue_codes else "warning"
        events.append(
            _event(
                sequence,
                "record_evaluated",
                None,
                item.record_id,
                item.observed_state,
                severity,
                item.adapter.content_address,
                "expected path matched" if item.accepted else "expected and observed paths differ",
            )
        )
        sequence += 1
    body = {"run_id": runtime.run_id, "events": tuple(events)}
    return ChromatinAlphaFrontierObservabilityReport(
        **body, accepted=all(event.content_address.startswith("sha256:") for event in events)
    )


def compare_chromatin_alpha_frontier_runs(
    left: ChromatinAlphaFrontierObservabilityReport,
    right: ChromatinAlphaFrontierObservabilityReport,
) -> dict[str, Any]:
    left_addresses = tuple(event.content_address for event in left.events)
    right_addresses = tuple(event.content_address for event in right.events)
    body = {
        "matching_event_count": len(left.events) == len(right.events),
        "matching_addresses": left_addresses == right_addresses,
        "left_address": left.content_address,
        "right_address": right.content_address,
    }
    return body | {
        "accepted": body["matching_event_count"] and body["matching_addresses"],
        "content_address": content_hash(body),
    }


__all__ = [
    "ChromatinAlphaFrontierEvent",
    "ChromatinAlphaFrontierObservabilityReport",
    "build_chromatin_alpha_frontier_trace",
    "compare_chromatin_alpha_frontier_runs",
]
