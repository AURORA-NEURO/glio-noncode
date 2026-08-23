"""public source registry."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignSourceRegistryPlane:
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


def build_editing_design_source_registry(**kwargs: Any) -> EditingDesignSourceRegistryPlane:
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
    values = {"source_ids": tuple(source.source_id for source in sources), "source_count": len(sources), "unique": len({source.source_id for source in sources}) == len(sources), "https": all(source.uri.startswith("https://") for source in sources)}
    accepted = bool(values["source_count"] == 5 and values["unique"] and values["https"])
    body = {"plane_id": "source_registry", "values": values, "accepted": accepted}
    return EditingDesignSourceRegistryPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignSourceRegistryPlane", "build_editing_design_source_registry"]
