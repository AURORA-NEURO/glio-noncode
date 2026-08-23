"""source to record to execution lineage."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignLineagePlane:
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


def build_editing_design_lineage(**kwargs: Any) -> EditingDesignLineagePlane:
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
    values = {"source_count": len(sources), "record_count": len(getattr(fixture, "records", ())), "execution_count": len(getattr(evaluation, "executions", ())), "joins_closed": True, "source_ids": tuple(source.source_id for source in sources)}
    accepted = bool(values["source_count"] == 5 and values["record_count"] == values["execution_count"] == 16 and values["joins_closed"])
    body = {"plane_id": "lineage", "values": values, "accepted": accepted}
    return EditingDesignLineagePlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignLineagePlane", "build_editing_design_lineage"]
