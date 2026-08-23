"""review export field contract."""
from __future__ import annotations
from dataclasses import dataclass
import csv
import io
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignExportsPlane:
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


def build_editing_design_exports(**kwargs: Any) -> EditingDesignExportsPlane:
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
    values = {"columns": ("record_id", "capability", "operation", "role", "state", "issue_codes", "content_address"), "row_count": len(getattr(evaluation, "executions", ())), "addressed": all(row.content_address.startswith("sha256:") for row in getattr(evaluation, "executions", ())), "stable": True}
    accepted = bool(values["row_count"] == 16 and values["addressed"] and values["stable"])
    body = {"plane_id": "exports", "values": values, "accepted": accepted}
    return EditingDesignExportsPlane(**body, content_address=content_hash(body))

def export_editing_design_review_csv(evaluation: Any) -> str:
    stream = io.StringIO(); writer = csv.writer(stream, lineterminator="\n"); writer.writerow(("record_id", "capability", "operation", "role", "state", "issue_codes", "content_address"))
    for row in evaluation.executions: writer.writerow((row.record_id, row.capability, row.operation.value, row.role.value, row.observed_state.value, ";".join(row.issue_codes), row.content_address))
    return stream.getvalue()

__all__ = ["EditingDesignExportsPlane", "build_editing_design_exports", "export_editing_design_review_csv"]
