"""repeatable instructions for resolving issue codes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignReviewProtocolPlane:
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


def build_validation_design_review_protocol(**kwargs: Any) -> ValidationDesignReviewProtocolPlane:
    fixture = kwargs.get("fixture")
    evaluation = kwargs.get("evaluation")
    quality = kwargs.get("quality")
    integrity = kwargs.get("integrity")
    depth = kwargs.get("depth")
    access = kwargs.get("access")
    adapters = kwargs.get("adapters")
    schema = kwargs.get("schema")
    sources = tuple(getattr(fixture, "sources", ()))
    stages = tuple(kwargs.get("stages", ()))
    steps = tuple(kwargs.get("steps", ()))
    run_id = str(kwargs.get("run_id", "validation-design-runtime"))
    fixture_id = str(getattr(fixture, "fixture_id", ""))
    values = {"steps": ("inspect exact payload", "confirm context boundary", "resolve each issue code", "rerun the same operation", "reconcile expected state", "retain the content address"), "issue_count": sum(len(row.issue_codes) for row in getattr(evaluation, "executions", ())), "held_rows": sum(bool(row.issue_codes) for row in getattr(evaluation, "executions", ())), "repeatable": True}
    accepted = bool(values["repeatable"] and values["held_rows"] > 0)
    body = {"plane_id": "review_protocol", "values": values, "accepted": accepted}
    return ValidationDesignReviewProtocolPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignReviewProtocolPlane", "build_validation_design_review_protocol"]
