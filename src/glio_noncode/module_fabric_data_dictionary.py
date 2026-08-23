"""Data dictionary for module-fabric input, evidence, and release fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FabricDictionaryEntry:
    field: str
    section: str
    type_name: str
    required: bool
    public_projection: bool
    invariant: str
    failure_state: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricDataDictionary:
    version: str
    entries: tuple[FabricDictionaryEntry, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_module_fabric_data_dictionary() -> FabricDataDictionary:
    rows = (
        ("fixture_id", "fixture", "string", True, True, "stable across replay", "review"),
        ("fixture_version", "fixture", "string", True, True, "matches contract version", "review"),
        ("evidence_boundary", "fixture", "enum", True, True, "public aggregate only", "abstained"),
        ("source_id", "source", "string", True, True, "joins a declared HTTPS receipt", "review"),
        ("uri", "source", "https_uri", True, True, "must start with https://", "review"),
        ("domain_id", "record", "domain enum", True, True, "matches capability prefix", "review"),
        ("capability_id", "record", "capability enum", True, True, "exists in 256-row catalog", "review"),
        ("role", "record", "positive/control", True, True, "control cannot promote", "review"),
        ("payload", "record", "object", True, False, "raw payload is not exported", "abstained"),
        ("observed_state", "execution", "state enum", True, True, "replay stable", "review"),
        ("issue_codes", "execution", "array string", True, True, "control reasons retained", "review"),
        ("content_address", "receipt", "sha256", True, True, "recomputed before release", "review"),
    )
    entries = tuple(FabricDictionaryEntry(*row) for row in rows)
    body = {"version": "module-fabric-dictionary-v1", "entries": entries}
    return FabricDataDictionary(**body, content_address=content_hash(body, prefix="module-fabric-dictionary"))


__all__ = ["FabricDataDictionary", "FabricDictionaryEntry", "default_module_fabric_data_dictionary"]
