"""public aggregate data boundary and receipt closure."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignPublicDataBoundaryPlane:
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


def build_validation_design_public_data_boundary(**kwargs: Any) -> ValidationDesignPublicDataBoundaryPlane:
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
    values = {"boundary": getattr(fixture, "evidence_boundary", ""), "source_count": len(sources), "record_count": len(getattr(fixture, "records", ())), "source_uris": tuple(source.uri for source in sources), "all_https": all(source.uri.startswith("https://") for source in sources), "no_private_markers": all(not any(marker in str(getattr(record, "payload", {})).lower() for marker in ("api_key", "password", "patient_id", "sample_id", "access_token")) for record in getattr(fixture, "records", ())) }
    accepted = bool(values["boundary"] == "public_aggregate_validation_design_planning" and values["source_count"] == 5 and values["record_count"] == 16 and values["all_https"] and values["no_private_markers"])
    body = {"plane_id": "public_data_boundary", "values": values, "accepted": accepted}
    return ValidationDesignPublicDataBoundaryPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignPublicDataBoundaryPlane", "build_validation_design_public_data_boundary"]
