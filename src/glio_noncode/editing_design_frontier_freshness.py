"""declared public receipt freshness."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignFreshnessPlane:
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


def build_editing_design_freshness(**kwargs: Any) -> EditingDesignFreshnessPlane:
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
    values = {"versions": tuple(source.version for source in sources), "declared": all(bool(source.version) for source in sources), "source_count": len(sources), "fixture_version": getattr(fixture, "fixture_version", "")}
    accepted = bool(values["declared"] and values["source_count"] == 5)
    body = {"plane_id": "freshness", "values": values, "accepted": accepted}
    return EditingDesignFreshnessPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignFreshnessPlane", "build_editing_design_freshness"]
