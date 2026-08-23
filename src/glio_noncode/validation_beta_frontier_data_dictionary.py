"""Data dictionary for public validation-beta evidence fields."""

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierDictionaryEntry:
    field_name: str
    value_kind: str
    semantic_role: str
    required: bool
    nullable: bool
    public: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_validation_beta_frontier_data_dictionary() -> tuple[ValidationBetaFrontierDictionaryEntry, ...]:
    values = (("context_key", "string", "exact six-field context identity", True, False), ("source_ids", "array[string]", "public source closure", True, False), ("expected_state", "enum", "fixture acceptance expectation", True, False), ("observed_state", "enum", "executed planner state", True, False), ("issue_codes", "array[string]", "blocking or review boundary", True, False), ("content_address", "string", "deterministic integrity receipt", True, False), ("raw_hash", "string", "row identity without raw payload export", True, False))
    return tuple(ValidationBetaFrontierDictionaryEntry(name, kind, role, required, nullable, True, content_hash({"field_name": name, "value_kind": kind}, prefix="validation-beta-dictionary-entry")) for name, kind, role, required, nullable in values)


__all__ = ["ValidationBetaFrontierDictionaryEntry", "default_validation_beta_frontier_data_dictionary"]
