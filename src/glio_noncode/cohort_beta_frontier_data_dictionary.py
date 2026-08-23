"""Data dictionary for review-safe C05-C08 fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierDictionaryEntry:
    field_name: str
    type_name: str
    definition: str
    example: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierDataDictionary:
    entries: tuple[CohortBetaFrontierDictionaryEntry, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_data_dictionary() -> CohortBetaFrontierDataDictionary:
    raw = (("context_key", "string", "exact execution context", "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"), ("variant_id", "string", "pseudonymous variant key", "v1"), ("sample_id", "string", "pseudonymous sample key", "s1"), ("callable_bases", "integer", "callable denominator", "1000"), ("support", "number", "bounded feature support", "0.9"), ("set_kind", "enum", "pathway or regulon namespace", "pathway"), ("disposition", "enum", "publication policy outcome", "publish"), ("content_address", "string", "stable receipt address", "sha256:..."))
    values = tuple(CohortBetaFrontierDictionaryEntry(field_name, type_name, definition, example, content_hash({"field_name": field_name, "type_name": type_name}, prefix="dictionary")) for field_name, type_name, definition, example in raw)
    return CohortBetaFrontierDataDictionary(values, content_hash(values, prefix="data-dictionary"))


__all__ = ["CohortBetaFrontierDataDictionary", "CohortBetaFrontierDictionaryEntry", "default_cohort_beta_frontier_data_dictionary"]
