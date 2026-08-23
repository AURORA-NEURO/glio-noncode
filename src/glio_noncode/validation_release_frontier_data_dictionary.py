"""Field dictionary for the D13 C13-C16 validation-release contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationReleaseField:
    name: str
    type: str
    required: bool
    meaning: str
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseDataDictionary:
    fields: tuple[ValidationReleaseField, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_validation_release_data_dictionary() -> ValidationReleaseDataDictionary:
    rows = (("context_key", "string", True, "exact six-part research context", "no implicit transport"), ("target_id", "string", True, "off-target target identity", "stable operation key"), ("on_target_score", "float[0,1]", True, "declared on-target score", "not an efficacy claim"), ("off_targets", "array[object]", True, "candidate burden observations", "aggregate planning input"), ("budget", "positive float", True, "planning cost budget", "resource boundary"), ("prerequisites", "array[string]", False, "dependency IDs", "cycle checked"), ("package_id", "string", True, "package identity", "content-addressed manifest"), ("evidence_address", "sha256 string", True, "result evidence receipt", "unknown or malformed results review"), ("claim_state", "string", True, "declared result classification", "does not prove truth"))
    fields = tuple(ValidationReleaseField(*row) for row in rows)
    return ValidationReleaseDataDictionary(fields, content_hash(fields))


__all__ = ["ValidationReleaseDataDictionary", "ValidationReleaseField", "default_validation_release_data_dictionary"]
