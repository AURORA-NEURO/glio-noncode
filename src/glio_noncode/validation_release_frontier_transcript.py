"""Ordered human-readable execution transcript."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationReleaseTranscriptEvent:
    sequence: int
    stage_id: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseTranscript:
    events: tuple[ValidationReleaseTranscriptEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_transcript(stage_ids: tuple[str, ...]) -> ValidationReleaseTranscript:
    events = []
    for sequence, stage_id in enumerate(stage_ids, start=1):
        body = {"sequence": sequence, "stage_id": stage_id, "detail": f"completed {stage_id}"}
        events.append(ValidationReleaseTranscriptEvent(**body, content_address=content_hash(body)))
    return ValidationReleaseTranscript(tuple(events), tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1)), content_hash(tuple(events)))


def verify_validation_release_transcript(transcript: ValidationReleaseTranscript) -> tuple[str, ...]:
    return () if transcript.accepted else ("transcript-order",)


__all__ = ["ValidationReleaseTranscript", "ValidationReleaseTranscriptEvent", "build_validation_release_transcript", "verify_validation_release_transcript"]
