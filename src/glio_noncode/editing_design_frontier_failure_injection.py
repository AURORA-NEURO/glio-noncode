"""malformed payload failure rehearsal."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable
from .editing_design_frontier_adapters import build_editing_design_adapters, execute_editing_design_adapter
from .editing_design_frontier_contracts import EditingDesignOperation

@dataclass(frozen=True, slots=True)
class EditingDesignFailureInjectionPlane:
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


def build_editing_design_failure_injection(**kwargs: Any) -> EditingDesignFailureInjectionPlane:
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
    registry = build_editing_design_adapters()
    cases = tuple({"case": operation.value, "state": execute_editing_design_adapter(registry, operation, {}).state.value, "issue_codes": execute_editing_design_adapter(registry, operation, {}).issue_codes, "required_state": "rejected"} for operation in EditingDesignOperation)
    values = {"cases": cases, "case_count": len(cases), "all_rejected": all(item["state"] == item["required_state"] for item in cases), "safe": all(item["issue_codes"] == ("schema_invalid",) for item in cases)}
    accepted = bool(values["case_count"] == 4 and values["all_rejected"] and values["safe"])
    body = {"plane_id": "failure_injection", "values": values, "accepted": accepted}
    return EditingDesignFailureInjectionPlane(**body, content_address=content_hash(body))

__all__ = ["EditingDesignFailureInjectionPlane", "build_editing_design_failure_injection"]
