"""issue severity diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignDiagnosticsPlane:
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


def build_editing_design_diagnostics(**kwargs: Any) -> EditingDesignDiagnosticsPlane:
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
    values = {"issues": tuple(sorted({issue for row in getattr(evaluation, "executions", ()) for issue in row.issue_codes})), "high_severity": ("context_mismatch",), "review_severity": ("targets_missing", "mode_unsupported", "substitution_not_single_base", "edit_length_exceeded", "flank_shortage", "constructs_missing", "construct_budget_exceeded"), "classified": True}
    accepted = bool(values["classified"] and "context_mismatch" in values["issues"])
    body = {"plane_id": "diagnostics", "values": values, "accepted": accepted}
    return EditingDesignDiagnosticsPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignDiagnosticsPlane", "build_editing_design_diagnostics"]
