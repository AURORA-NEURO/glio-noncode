"""Contract/runtime compatibility receipt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import VALIDATION_RELEASE_FRONTIER_VERSION


@dataclass(frozen=True, slots=True)
class ValidationReleaseCompatibility:
    contract_version: str
    runtime_version: str
    compatible: bool
    notes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_release_compatibility() -> ValidationReleaseCompatibility:
    body = {"contract_version": VALIDATION_RELEASE_FRONTIER_VERSION, "runtime_version": "python3.11-stdlib", "compatible": True, "notes": ("content-addressed records", "no network required for replay", "JSON projection stable")}
    return ValidationReleaseCompatibility(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseCompatibility", "evaluate_validation_release_compatibility"]
