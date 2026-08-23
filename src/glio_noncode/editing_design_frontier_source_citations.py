"""source citation index."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignSourceCitationsPlane:
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


def build_editing_design_source_citations(**kwargs: Any) -> EditingDesignSourceCitationsPlane:
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
    values = {"citations": tuple({"source_id": source.source_id, "uri": source.uri, "scope": source.scope} for source in sources), "citation_count": len(sources), "https": all(source.uri.startswith("https://") for source in sources), "scoped": all(source.scope for source in sources)}
    accepted = bool(values["citation_count"] == 5 and values["https"] and values["scoped"])
    body = {"plane_id": "source_citations", "values": values, "accepted": accepted}
    return EditingDesignSourceCitationsPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignSourceCitationsPlane", "build_editing_design_source_citations"]
