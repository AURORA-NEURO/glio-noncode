"""Replayable transcript for the ordered control frontier runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_runtime import ControlFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierTranscriptEvent:
    sequence: int
    stage_id: str
    state: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierTranscript:
    run_id: str
    events: tuple[ControlFrontierTranscriptEvent, ...]
    stage_count: int
    contiguous: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_transcript(runtime: ControlFrontierRuntimeReport) -> ControlFrontierTranscript:
    """Project runtime stages into a compact replay transcript."""

    events = []
    for stage in runtime.stages:
        body = {
            "sequence": stage.sequence,
            "stage_id": stage.stage_id,
            "state": stage.state,
            "output_address": stage.output_address,
            "detail": stage.detail,
        }
        events.append(ControlFrontierTranscriptEvent(**body, content_address=content_hash(body)))
    event_tuple = tuple(events)
    contiguous = tuple(item.sequence for item in event_tuple) == tuple(range(1, len(event_tuple) + 1))
    accepted = contiguous and len({item.stage_id for item in event_tuple}) == len(event_tuple) and all(item.output_address.startswith("sha256:") for item in event_tuple)
    body = {"run_id": runtime.run_id, "events": event_tuple, "stage_count": len(event_tuple), "contiguous": contiguous, "accepted": accepted}
    return ControlFrontierTranscript(**body, content_address=content_hash(body))


def verify_control_frontier_transcript(transcript: ControlFrontierTranscript) -> tuple[str, ...]:
    """Return stable issue IDs for transcript defects."""

    issues = []
    if not transcript.contiguous:
        issues.append("non_contiguous_sequence")
    if transcript.stage_count != len(transcript.events):
        issues.append("stage_count_mismatch")
    if len({item.stage_id for item in transcript.events}) != len(transcript.events):
        issues.append("duplicate_stage_id")
    if any(not item.output_address.startswith("sha256:") for item in transcript.events):
        issues.append("invalid_output_address")
    return tuple(issues)


__all__ = ["ControlFrontierTranscript", "ControlFrontierTranscriptEvent", "build_control_frontier_transcript", "verify_control_frontier_transcript"]
