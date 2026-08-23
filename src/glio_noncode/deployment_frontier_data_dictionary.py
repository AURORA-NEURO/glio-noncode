"""Data dictionary for the deployment frontier export contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDictionaryEntry:
    field_id: str
    type_name: str
    required: bool
    nullable: bool
    sensitivity: str
    meaning: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDataDictionary:
    version: str
    entries: tuple[DeploymentFrontierDictionaryEntry, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_deployment_frontier_data_dictionary() -> DeploymentFrontierDataDictionary:
    rows = (
        ("context_key", "string", True, False, "public", "exact join context"),
        ("record_id", "string", True, False, "public", "stable fixture row identity"),
        ("operation", "enum", True, False, "public", "deployment operation family"),
        ("role", "enum", True, False, "public", "positive or control row"),
        ("state", "enum", True, False, "public", "observed boundary state"),
        ("issue_codes", "array[string]", True, False, "public", "normalized denial reasons"),
        ("content_address", "sha256", True, False, "public", "content address for replay"),
        ("patient_level", "boolean", True, False, "public", "must remain false"),
    )
    entries = []
    for field_id, type_name, required, nullable, sensitivity, meaning in rows:
        body = {"field_id": field_id, "type_name": type_name, "required": required, "nullable": nullable, "sensitivity": sensitivity, "meaning": meaning}
        entries.append(DeploymentFrontierDictionaryEntry(**body, content_address=deployment_address(body)))
    return DeploymentFrontierDataDictionary("deployment-frontier-dictionary-v1", tuple(entries), deployment_address(tuple(entries)))


__all__ = ["DeploymentFrontierDataDictionary", "DeploymentFrontierDictionaryEntry", "default_deployment_frontier_data_dictionary"]
