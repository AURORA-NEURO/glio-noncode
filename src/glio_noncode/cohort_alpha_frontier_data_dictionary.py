"""Data dictionary for the public C09-C12 fixture and release objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_schema import CohortAlphaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierDictionaryEntry:
    name: str
    value_type: str
    semantic_role: str
    null_behavior: str
    operations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierDataDictionary:
    entries: tuple[CohortAlphaFrontierDictionaryEntry, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_data_dictionary(schema: CohortAlphaFrontierSchemaReport) -> CohortAlphaFrontierDataDictionary:
    entries = tuple(CohortAlphaFrontierDictionaryEntry(field.name, field.value_type, field.role, field.null_policy, (field.operation,), content_hash({"name": field.name, "type": field.value_type, "role": field.role, "null": field.null_policy, "operation": field.operation}, prefix="alpha-dictionary")) for field in schema.fields)
    return CohortAlphaFrontierDataDictionary(entries, len(entries) == 17 and len({(item.operations[0], item.name) for item in entries}) == len(entries) and all(item.value_type and item.null_behavior for item in entries), content_hash(entries, prefix="alpha-dictionary-report"))


__all__ = ["CohortAlphaFrontierDataDictionary", "CohortAlphaFrontierDictionaryEntry", "build_cohort_alpha_frontier_data_dictionary"]
