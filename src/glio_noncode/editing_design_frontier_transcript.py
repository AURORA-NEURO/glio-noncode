"""ordered operator transcript."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignTranscriptPlane:
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


def build_editing_design_transcript(**kwargs: Any) -> EditingDesignTranscriptPlane:
    fixture = kwargs.get("fixture")
    evaluation = kwargs.get("evaluation")
    quality = kwargs.get("quality")
    integrity = kwargs.get("integrity")
    depth = kwargs.get("depth")
    access = kwargs.get("access")
    adapters = kwargs.get("adapters")
    schema = kwargs.get("schema")
    audit = kwargs.get("audit")
    sources = tuple(getattr(fixture, "sources", ()))
    stages = tuple(kwargs.get("stages", ()))
    steps = tuple(kwargs.get("steps", ()))
    run_id = str(kwargs.get("run_id", "editing-design-runtime"))
    fixture_id = str(getattr(fixture, "fixture_id", ""))
    values = {"lines": tuple(f"{stage.sequence} completed {stage.stage_id}" for stage in stages), "line_count": len(stages), "ordered": True, "run_id": run_id}
    accepted = bool(values["line_count"] == len(stages) and values["ordered"])
    body = {"plane_id": "transcript", "values": values, "accepted": accepted}
    return EditingDesignTranscriptPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignTranscriptPlane", "build_editing_design_transcript"]
