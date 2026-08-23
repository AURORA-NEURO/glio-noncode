"""Data dictionary for the public aggregate and review outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFoundationDataDictionaryEntry:
    field_id: str
    type_name: str
    semantic_role: str
    unit: str
    nullable: bool
    allowed_values: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationDataDictionary:
    dictionary_id: str
    entries: tuple[CohortFoundationDataDictionaryEntry, ...]
    accepted: bool
    content_address: str

    def by_field(self, field_id: str) -> CohortFoundationDataDictionaryEntry:
        return next(item for item in self.entries if item.field_id == field_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_foundation_frontier_data_dictionary() -> CohortFoundationDataDictionary:
    definitions = (
        ("context_key", "string", "exact applicability context", "identifier", False, ()),
        ("record_id", "string", "pseudonymous aggregate row identity", "identifier", False, ()),
        ("callable_bases", "integer", "available callable denominator", "bases", False, ()),
        ("background_rate", "float", "descriptive observed/callable ratio", "per_base", True, ()),
        ("sequence_context", "string", "bounded sequence window", "bases", True, ()),
        ("chromatin_features", "object", "normalized feature vector", "unit_interval", False, ()),
        ("disposition", "enum", "publication control decision", "category", False, ("allow_descriptive", "review", "quarantine")),
        ("content_address", "string", "deterministic evidence receipt", "digest", False, ()),
    )
    entries = tuple(CohortFoundationDataDictionaryEntry(field_id, type_name, role, unit, nullable, allowed, content_hash((field_id, type_name, role, unit, nullable, allowed))) for field_id, type_name, role, unit, nullable, allowed in definitions)
    body = {"dictionary_id": "cohort-foundation-frontier-data-dictionary", "entries": entries}
    return CohortFoundationDataDictionary(body["dictionary_id"], entries, len(entries) == 8 and all(item.field_id and item.type_name for item in entries), content_hash(body))


__all__ = ["CohortFoundationDataDictionary", "CohortFoundationDataDictionaryEntry", "default_cohort_foundation_frontier_data_dictionary"]
