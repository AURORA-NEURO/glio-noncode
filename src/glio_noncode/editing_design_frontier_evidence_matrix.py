"""source and scenario evidence matrix."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignEvidenceMatrixPlane:
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


def build_editing_design_evidence_matrix(**kwargs: Any) -> EditingDesignEvidenceMatrixPlane:
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
    values = {"record_count": len(getattr(fixture, "records", ())), "source_count": len(sources), "known_source_joins": all(set(row.source_ids) <= {source.source_id for source in sources} for row in getattr(fixture, "records", ())), "execution_addresses": all(row.content_address.startswith("sha256:") for row in getattr(evaluation, "executions", ())) }
    accepted = bool(values["record_count"] == 16 and values["source_count"] == 5 and values["known_source_joins"] and values["execution_addresses"])
    body = {"plane_id": "evidence_matrix", "values": values, "accepted": accepted}
    return EditingDesignEvidenceMatrixPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignEvidenceMatrixPlane", "build_editing_design_evidence_matrix"]
