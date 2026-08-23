"""Source receipt registry projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseFixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseSourceRegistry:
    source_ids: tuple[str, ...]
    source_uris: dict[str, str]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_source_registry(fixture: ValidationReleaseFixture) -> ValidationReleaseSourceRegistry:
    source_uris = {item.source_id: item.uri for item in fixture.sources}
    body = {"source_ids": tuple(sorted(source_uris)), "source_uris": source_uris, "accepted": len(source_uris) == len(fixture.sources) and all(uri.startswith("https://") for uri in source_uris.values())}
    return ValidationReleaseSourceRegistry(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseSourceRegistry", "build_validation_release_source_registry"]
