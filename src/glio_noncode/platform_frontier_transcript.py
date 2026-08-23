"""Replayable ordered transcript for platform runtime stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierTranscriptEvent:
    sequence: int
    stage_id: str
    state: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierTranscript:
    run_id: str
    events: tuple[PlatformFrontierTranscriptEvent, ...]
    stage_count: int
    contiguous: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_transcript(run_id: str, stages: tuple[dict[str, Any], ...]) -> PlatformFrontierTranscript:
    events = []
    for sequence, stage in enumerate(stages, start=1):
        body = {"sequence": sequence, "stage_id": str(stage["stage_id"]), "state": str(stage.get("state", "completed")), "output_address": str(stage["output_address"]), "detail": str(stage.get("detail", ""))}
        events.append(PlatformFrontierTranscriptEvent(**body, content_address=content_hash(body)))
    contiguous = tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1))
    accepted = contiguous and len({item.stage_id for item in events}) == len(events) and all(item.output_address.startswith("sha256:") for item in events)
    body = {"run_id": run_id, "events": tuple(events), "stage_count": len(events), "contiguous": contiguous, "accepted": accepted}
    return PlatformFrontierTranscript(**body, content_address=content_hash(body))


def verify_platform_frontier_transcript(transcript: PlatformFrontierTranscript) -> tuple[str, ...]:
    issues = []
    if not transcript.contiguous:
        issues.append("non_contiguous_sequence")
    if transcript.stage_count != len(transcript.events):
        issues.append("stage_count_mismatch")
    if len({item.stage_id for item in transcript.events}) != len(transcript.events):
        issues.append("duplicate_stage_id")
    return tuple(issues)


__all__ = ["PlatformFrontierTranscript", "PlatformFrontierTranscriptEvent", "build_platform_frontier_transcript", "verify_platform_frontier_transcript"]
