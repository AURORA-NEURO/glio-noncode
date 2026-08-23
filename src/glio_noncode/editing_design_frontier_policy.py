"""research-use policy disposition."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EditingDesignPolicyPlane:
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


def build_editing_design_policy(**kwargs: Any) -> EditingDesignPolicyPlane:
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
    values = {"permitted": ("design planning", "aggregate replay", "review routing"), "prohibited": ("clinical efficacy", "individual diagnosis", "causal certainty"), "state_actions": {"designed": "retain", "review": "assign reviewer", "blocked": "quarantine", "rejected": "repair"}, "research_only": True}
    accepted = bool(values["research_only"] and len(values["state_actions"]) == 4)
    body = {"plane_id": "policy", "values": values, "accepted": accepted}
    return EditingDesignPolicyPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignPolicyPlane", "build_editing_design_policy"]
