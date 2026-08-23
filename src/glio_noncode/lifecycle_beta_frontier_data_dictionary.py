"""Data dictionary for the C05-C12 public aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_schema import default_lifecycle_beta_frontier_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierDataDictionaryEntry:
    field_name: str
    type_name: str
    required: bool
    permitted_values: tuple[str, ...]
    boundary: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierDataDictionary:
    entries: tuple[LifecycleBetaFrontierDataDictionaryEntry, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_lifecycle_beta_frontier_data_dictionary() -> LifecycleBetaFrontierDataDictionary:
    schema = default_lifecycle_beta_frontier_schema()
    entries = []
    for field in schema.fields:
        values = ("positive", "control") if field.name == "role" else tuple(item.value for item in schema.operations) if field.name == "operation" else ()
        body = {"field_name": field.name, "type_name": field.value_type, "required": field.required, "permitted_values": values, "boundary": "public aggregate; exact context required"}
        entries.append(LifecycleBetaFrontierDataDictionaryEntry(**body, content_address=content_hash(body)))
    return LifecycleBetaFrontierDataDictionary(tuple(entries), content_hash({"entries": tuple(entries)}))


__all__ = ["LifecycleBetaFrontierDataDictionary", "LifecycleBetaFrontierDataDictionaryEntry", "default_lifecycle_beta_frontier_data_dictionary"]
