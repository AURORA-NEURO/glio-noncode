"""Data dictionary for operation payloads and emitted measurements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierDataDictionaryEntry:
    field: str
    operation: str
    type_name: str
    required: bool
    definition: str
    valid_range: str
    output_or_input: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierDataDictionary:
    entries: tuple[LinkGraphAlphaFrontierDataDictionaryEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def fields_for(self, operation: str) -> tuple[LinkGraphAlphaFrontierDataDictionaryEntry, ...]:
        return tuple(item for item in self.entries if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_data_dictionary() -> LinkGraphAlphaFrontierDataDictionary:
    rows = []
    common = (("variant_id", "string", True, "variant identity", "non-empty", "input"), ("element_id", "string", True, "regulatory element identity", "non-empty", "input"), ("gene_id", "string", True, "candidate gene identity", "non-empty", "input"), ("context_key", "string", True, "six-dimensional context key", "pipe-delimited", "input"), ("source_id", "string", True, "source receipt identifier", "non-empty", "input"))
    for operation in LinkGraphAlphaFrontierOperation:
        for field, type_name, required, definition, valid_range, direction in common:
            rows.append(LinkGraphAlphaFrontierDataDictionaryEntry(field, operation.value, type_name, required, definition, valid_range, direction))
    rows.extend((LinkGraphAlphaFrontierDataDictionaryEntry("state", "all", "enum", True, "bounded result state", "closed state enum", "output"), LinkGraphAlphaFrontierDataDictionaryEntry("issue_codes", "all", "array[string]", False, "review and boundary issues", "known issue codes", "output"), LinkGraphAlphaFrontierDataDictionaryEntry("content_address", "all", "string", True, "content hash of result", "sha256 prefix", "output")))
    return LinkGraphAlphaFrontierDataDictionary(tuple(rows), len(rows) == 23)


__all__ = ["LinkGraphAlphaFrontierDataDictionary", "LinkGraphAlphaFrontierDataDictionaryEntry", "build_link_graph_alpha_frontier_data_dictionary"]
