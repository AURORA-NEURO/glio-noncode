"""Public surface and data-access boundary receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseFixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseAccessManifest:
    fixture_id: str
    public_sources: tuple[str, ...]
    allowed_formats: tuple[str, ...]
    patient_level_data: bool
    network_fetch_during_replay: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_access_manifest(fixture: ValidationReleaseFixture) -> ValidationReleaseAccessManifest:
    body = {"fixture_id": fixture.fixture_id, "public_sources": tuple(item.uri for item in fixture.sources), "allowed_formats": ("json", "csv", "markdown"), "patient_level_data": False, "network_fetch_during_replay": False, "accepted": True}
    return ValidationReleaseAccessManifest(**body, content_address=content_hash(body))


def audit_validation_release_access(manifest: ValidationReleaseAccessManifest) -> tuple[str, ...]:
    errors = []
    if manifest.patient_level_data:
        errors.append("patient-level-data")
    if manifest.network_fetch_during_replay:
        errors.append("network-fetch-during-replay")
    if not all(uri.startswith("https://") for uri in manifest.public_sources):
        errors.append("non-https-source")
    return tuple(errors)


__all__ = ["ValidationReleaseAccessManifest", "audit_validation_release_access", "build_validation_release_access_manifest"]
