"""Human-readable deterministic transcript of deployment stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierTranscriptEvent:
    sequence: int
    stage_id: str
    sentence: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierTranscript:
    events: tuple[DeploymentFrontierTranscriptEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_transcript(stage_ids: tuple[str, ...]) -> DeploymentFrontierTranscript:
    events = []
    for sequence, stage_id in enumerate(stage_ids, start=1):
        body = {"sequence": sequence, "stage_id": stage_id, "sentence": f"Stage {sequence} completed: {stage_id}."}
        events.append(DeploymentFrontierTranscriptEvent(**body, content_address=deployment_address(body)))
    return DeploymentFrontierTranscript(tuple(events), tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1)), deployment_address(tuple(events)))


def verify_deployment_frontier_transcript(transcript: DeploymentFrontierTranscript) -> tuple[str, ...]:
    return () if transcript.accepted else ("transcript_sequence",)


__all__ = ["DeploymentFrontierTranscript", "DeploymentFrontierTranscriptEvent", "build_deployment_frontier_transcript", "verify_deployment_frontier_transcript"]
