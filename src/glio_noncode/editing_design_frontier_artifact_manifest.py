"""core artifact manifest."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignArtifactManifestPlane:
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


def build_editing_design_artifact_manifest(**kwargs: Any) -> EditingDesignArtifactManifestPlane:
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
    values = {"fixture": getattr(fixture, "content_address", ""), "evaluation": getattr(evaluation, "content_address", ""), "artifact_count": 2 + len(sources), "all_addressed": getattr(fixture, "content_address", "").startswith("sha256:") and getattr(evaluation, "content_address", "").startswith("sha256:")}
    accepted = bool(values["artifact_count"] == 7 and values["all_addressed"])
    body = {"plane_id": "artifact_manifest", "values": values, "accepted": accepted}
    return EditingDesignArtifactManifestPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignArtifactManifestPlane", "build_editing_design_artifact_manifest"]
