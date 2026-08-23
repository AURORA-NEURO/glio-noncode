"""field dictionary for stable planning artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignDataDictionaryPlane:
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


def build_validation_design_data_dictionary(**kwargs: Any) -> ValidationDesignDataDictionaryPlane:
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
    values = {"fixture_fields": ("fixture_id", "fixture_version", "context_key", "evidence_boundary", "sources", "records", "content_address"), "record_fields": ("record_id", "capability", "operation", "role", "context_key", "source_ids", "payload", "expected_state", "expected_issue_codes", "content_address"), "execution_fields": ("observed_state", "issue_codes", "output", "content_address"), "field_count": 20}
    accepted = bool(values["field_count"] == 20)
    body = {"plane_id": "data_dictionary", "values": values, "accepted": accepted}
    return ValidationDesignDataDictionaryPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignDataDictionaryPlane", "build_validation_design_data_dictionary"]
