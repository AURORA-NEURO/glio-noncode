"""Data dictionary for C01-C04 inputs and outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierDataDictionaryEntry:
    operation: str
    field: str
    type_name: str
    required: bool
    definition: str
    direction: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierDataDictionary:
    entries: tuple[LinkGraphFoundationFrontierDataDictionaryEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def fields_for(self, operation: str) -> tuple[LinkGraphFoundationFrontierDataDictionaryEntry, ...]:
        return tuple(item for item in self.entries if item.operation in {operation, "all"})

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_data_dictionary() -> LinkGraphFoundationFrontierDataDictionary:
    common = (("variant", "object", True, "variant identity", "input"), ("context_key", "string", True, "context gate", "input"), ("source_ids", "array[string]", True, "source receipt linkage", "input"), ("state", "enum", True, "bounded result state", "output"), ("issue_codes", "array[string]", False, "review issue codes", "output"), ("content_address", "string", True, "content hash", "output"))
    entries = tuple(LinkGraphFoundationFrontierDataDictionaryEntry(operation.value, field, type_name, required, definition, direction) for operation in LinkGraphFoundationFrontierOperation for field, type_name, required, definition, direction in common)
    return LinkGraphFoundationFrontierDataDictionary(entries, len(entries) == 24)


__all__ = ["LinkGraphFoundationFrontierDataDictionary", "LinkGraphFoundationFrontierDataDictionaryEntry", "build_link_graph_foundation_frontier_data_dictionary"]
