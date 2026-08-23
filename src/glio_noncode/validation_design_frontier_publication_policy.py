"""publication policy for safe aggregate artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignPublicationPolicyPlane:
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


def build_validation_design_publication_policy(**kwargs: Any) -> ValidationDesignPublicationPolicyPlane:
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
    values = {"boundary": getattr(fixture, "evidence_boundary", ""), "allowed": ("fixture", "evaluation", "review export", "aggregate report"), "denied": ("private credentials", "individual records", "clinical conclusion"), "decision": "publish aggregate only"}
    accepted = bool(values["boundary"] == "public_aggregate_validation_design_planning" and values["decision"] == "publish aggregate only")
    body = {"plane_id": "publication_policy", "values": values, "accepted": accepted}
    return ValidationDesignPublicationPolicyPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignPublicationPolicyPlane", "build_validation_design_publication_policy"]
