"""Field-level public data dictionary for control frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierDictionaryEntry:
    field: str
    type_name: str
    required: bool
    boundary: str
    description: str
    example: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierDataDictionary:
    dictionary_id: str
    version: str
    entries: tuple[ControlFrontierDictionaryEntry, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_control_frontier_data_dictionary() -> ControlFrontierDataDictionary:
    rows = (
        ("record_id", "string", True, "aggregate", "stable non-patient row identity", "C05-POS-001"),
        ("operation", "enum", True, "aggregate", "one of eight allowlisted control operations", "policy_claim_gate"),
        ("role", "enum", True, "aggregate", "positive or control fixture role", "control"),
        ("context_key", "string", True, "exact", "reference build, disease, age, state, scope, treatment tuple", "GRCh38|glioma|adult|stem_like|core|untreated"),
        ("source_ids", "array[string]", True, "public", "receipts supporting the aggregate row", ["src-policy"]),
        ("state", "enum", True, "operational", "observed state, not a scientific conclusion", "blocked"),
        ("issue_codes", "array[string]", True, "operational", "explicit blockers, warnings, or empty tuple", ["source_allowlist_gap"]),
        ("output", "object", True, "projection", "structured adapter output without raw private data", {"allowed": False}),
        ("content_address", "sha256", True, "integrity", "address of the receipt body", "sha256:..."),
        ("research_only", "boolean", True, "policy", "release-use restriction", True),
    )
    entries = []
    for field, type_name, required, boundary, description, example in rows:
        body = {"field": field, "type_name": type_name, "required": required, "boundary": boundary, "description": description, "example": example}
        entries.append(ControlFrontierDictionaryEntry(**body, content_address=content_hash(body)))
    body = {"dictionary_id": "control-frontier-public-dictionary", "version": "v1", "entries": tuple(entries)}
    return ControlFrontierDataDictionary(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierDataDictionary", "ControlFrontierDictionaryEntry", "default_control_frontier_data_dictionary"]
