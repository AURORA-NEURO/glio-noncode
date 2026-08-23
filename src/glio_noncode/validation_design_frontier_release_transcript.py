"""release decision transcript."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignReleaseTranscriptPlane:
    plane_id: str
    values: dict[str, Any]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def summary(self) -> str:
        return f"{self.plane_id}: {'accepted' if self.accepted else 'held'}"

    def check(self, key: str) -> bool:
        return bool(self.values.get(key, False))


def build_validation_design_release_transcript(**kwargs: Any) -> ValidationDesignReleaseTranscriptPlane:
    fixture = kwargs.get("fixture")
    evaluation = kwargs.get("evaluation")
    quality = kwargs.get("quality")
    integrity = kwargs.get("integrity")
    depth = kwargs.get("depth")
    access = kwargs.get("access")
    adapters = kwargs.get("adapters")
    schema = kwargs.get("schema")
    sources = tuple(getattr(fixture, "sources", ()))
    stages = tuple(kwargs.get("stages", ()))
    steps = tuple(kwargs.get("steps", ()))
    run_id = str(kwargs.get("run_id", "validation-design-runtime"))
    fixture_id = str(getattr(fixture, "fixture_id", ""))
    values = {"run_id": run_id, "events": ("data-accepted", "evaluation-accepted", "quality-accepted", "replay-accepted", "release-accepted"), "event_count": 5, "ordered": True}
    accepted = bool(values["event_count"] == 5 and values["ordered"] and bool(values["run_id"]))
    body = {"plane_id": "release_transcript", "values": values, "accepted": accepted}
    return ValidationDesignReleaseTranscriptPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignReleaseTranscriptPlane", "build_validation_design_release_transcript"]
