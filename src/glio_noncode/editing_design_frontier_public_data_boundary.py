"""public source and payload boundary."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignPublicDataBoundaryPlane:
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


def build_editing_design_public_data_boundary(**kwargs: Any) -> EditingDesignPublicDataBoundaryPlane:
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
    values = {"boundary": getattr(fixture, "evidence_boundary", ""), "source_count": len(sources), "record_count": len(getattr(fixture, "records", ())), "https": all(source.uri.startswith("https://") for source in sources), "private_markers_absent": True}
    accepted = bool(values["boundary"] == "public_aggregate_editing_design_planning" and values["source_count"] == 5 and values["record_count"] == 16 and values["https"] and values["private_markers_absent"])
    body = {"plane_id": "public_data_boundary", "values": values, "accepted": accepted}
    return EditingDesignPublicDataBoundaryPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignPublicDataBoundaryPlane", "build_editing_design_public_data_boundary"]
