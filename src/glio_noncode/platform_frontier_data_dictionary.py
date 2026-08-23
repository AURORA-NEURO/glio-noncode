"""Field dictionary for platform frontier JSON and CSV projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierDictionaryEntry:
    field: str
    type_name: str
    scope: str
    required: bool
    meaning: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierDataDictionary:
    entries: tuple[PlatformFrontierDictionaryEntry, ...]
    field_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_platform_frontier_data_dictionary() -> PlatformFrontierDataDictionary:
    rows = [
        ("fixture_id", "string", "fixture", True, "stable fixture identity"),
        ("context_key", "string", "fixture/record", True, "exact operational context"),
        ("evidence_boundary", "string", "fixture", True, "limit of supported evidence"),
        ("record_id", "string", "record/execution", True, "stable row identity"),
        ("operation", "enum", "record/execution", True, "one of C01-C04"),
        ("role", "enum", "record/execution", True, "positive or control"),
        ("expected_state", "enum", "record", True, "fixture declaration"),
        ("state", "enum", "execution", True, "observed operation state"),
        ("issue_codes", "array[string]", "execution", True, "explicit control reasons"),
        ("content_address", "sha256", "all", True, "canonical object address"),
        ("mission_id", "string", PlatformFrontierOperation.MISSION_PLANNER.value, True, "bounded planning identity"),
        ("workflow_id", "string", PlatformFrontierOperation.WORKFLOW_COMPILER.value, True, "compiled workflow identity"),
        ("tool_id", "string", PlatformFrontierOperation.TYPED_TOOL_REGISTRY.value, True, "registered tool identity"),
        ("request_id", "string", PlatformFrontierOperation.EXECUTION_SANDBOX.value, True, "invocation identity"),
    ]
    entries = []
    for field, type_name, scope, required, meaning in rows:
        body = {"field": field, "type_name": type_name, "scope": scope, "required": required, "meaning": meaning}
        entries.append(PlatformFrontierDictionaryEntry(**body, content_address=content_hash(body)))
    return PlatformFrontierDataDictionary(tuple(entries), len(entries), len(entries) == 14, content_hash(tuple(entries)))


__all__ = ["PlatformFrontierDataDictionary", "PlatformFrontierDictionaryEntry", "default_platform_frontier_data_dictionary"]
