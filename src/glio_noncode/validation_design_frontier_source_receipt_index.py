"""indexed source receipt lookup."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignSourceReceiptIndexPlane:
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


def build_validation_design_source_receipt_index(**kwargs: Any) -> ValidationDesignSourceReceiptIndexPlane:
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
    values = {"index": {source.source_id: {"uri": source.uri, "address": source.content_address} for source in sources}, "source_count": len(sources), "unique": len({source.source_id for source in sources}) == len(sources), "https": all(source.uri.startswith("https://") for source in sources)}
    accepted = bool(values["source_count"] == 5 and values["unique"] and values["https"])
    body = {"plane_id": "source_receipt_index", "values": values, "accepted": accepted}
    return ValidationDesignSourceReceiptIndexPlane(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignSourceReceiptIndexPlane", "build_validation_design_source_receipt_index"]
